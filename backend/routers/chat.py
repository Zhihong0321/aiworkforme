from copy import deepcopy
from fastapi import APIRouter, Depends, HTTPException, Body
import asyncio
from sqlmodel import Session, select
from typing import List, Dict, Any, Optional
import json
import logging
import os
import re
import time
from openai import RateLimitError

from src.infra.database import get_session
from src.adapters.db.agent_models import Agent, AgentMCPServer
from src.adapters.db.mcp_models import MCPServer
from src.adapters.db.chat_models import ChatRequest, ChatResponse, ChatSession, ChatMessage
from src.adapters.api.dependencies import (
    AuthContext,
    get_llm_router,
    get_mcp_manager,
    require_tenant_access,
)
from src.adapters.mcp.manager import MCPManager
from src.app.conversation_skills import (
    ConversationTaskKind,
    compose_conversation_prompt,
    get_default_conversation_skill_registry,
)
from src.infra.llm.router import LLMRouter
from src.infra.llm.schemas import LLMTask, LLMMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

CALENDAR_TOOL_NAMES = {"book_appointment", "get_user_availability", "create_pending_appointment"}
SCHEDULING_KEYWORDS = (
    "appoint",
    "appointment",
    "availability",
    "available",
    "book",
    "booking",
    "calendar",
    "meeting",
    "reschedule",
    "schedule",
    "slot",
    "time slot",
)
SCHEDULING_TIME_PATTERN = re.compile(
    r"\b(?:\d{1,2}(?::\d{2})?\s?(?:am|pm)|tomorrow|today|next week|next monday|next tuesday|next wednesday|next thursday|next friday|next saturday|next sunday|\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
CALENDAR_TOOL_RULES = (
    "CALENDAR TOOL RULES:\n"
    "- For calendar, scheduling, availability, booking, rescheduling, or appointment requests, you must call the relevant calendar tool before answering.\n"
    "- Never say an appointment is booked, scheduled, confirmed, moved, or cancelled unless the tool result explicitly succeeded.\n"
    "- If the request lacks date or time details, ask a follow-up question instead of pretending it is booked.\n"
    "- The system injects authenticated calendar identity automatically. Do not ask the user for internal tenant_id or agent_id, and do not invent them."
)


def _is_calendar_tool(tool_name: str) -> bool:
    return str(tool_name or "").strip() in CALENDAR_TOOL_NAMES


def _is_scheduling_request(message: str) -> bool:
    text = str(message or "").strip().lower()
    if not text:
        return False
    if any(keyword in text for keyword in SCHEDULING_KEYWORDS):
        return True
    return bool(SCHEDULING_TIME_PATTERN.search(text))


def _sanitize_chat_tool(tool_def: Dict[str, Any]) -> Dict[str, Any]:
    tool_name = str(tool_def.get("name") or "").strip()
    description = str(tool_def.get("description") or "").strip()
    parameters = deepcopy(tool_def.get("inputSchema") or {"type": "object", "properties": {}})

    if _is_calendar_tool(tool_name):
        properties = dict(parameters.get("properties") or {})
        properties.pop("tenant_id", None)
        properties.pop("agent_id", None)
        parameters["properties"] = properties

        required = [
            item
            for item in list(parameters.get("required") or [])
            if item not in {"tenant_id", "agent_id"}
        ]
        if required:
            parameters["required"] = required
        else:
            parameters.pop("required", None)

        description = (
            f"{description} Authenticated calendar identity is injected automatically."
            if description
            else "Authenticated calendar identity is injected automatically."
        )

    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": description or None,
            "parameters": parameters,
        },
    }


def _inject_authenticated_tool_args(
    tool_name: str,
    tool_args: Dict[str, Any],
    *,
    auth: AuthContext,
    agent: Agent,
) -> Dict[str, Any]:
    resolved_args = dict(tool_args or {})
    if _is_calendar_tool(tool_name):
        resolved_args["tenant_id"] = int(auth.tenant.id)
        resolved_args["agent_id"] = int(agent.id)
    return resolved_args

def save_message(
    session: Session, 
    chat_session_id: int, 
    role: str, 
    content: str, 
    tenant_id: Optional[int] = None,
    tool_calls: Optional[List[Dict]] = None,
    tool_call_id: Optional[str] = None
):
    tool_calls_str = json.dumps(tool_calls) if tool_calls else None
    msg = ChatMessage(
        chat_session_id=chat_session_id, 
        tenant_id=tenant_id,
        role=role, 
        content=content or "", 
        tool_calls=tool_calls_str,
        tool_call_id=tool_call_id
    )
    session.add(msg)
    session.commit()

@router.post("/", response_model=ChatResponse)
async def chat_with_agent(
    request: ChatRequest, 
    session: Session = Depends(get_session),
    mcp_manager: MCPManager = Depends(get_mcp_manager),
    llm_router: LLMRouter = Depends(get_llm_router),
    auth: AuthContext = Depends(require_tenant_access),
):
    try:
        t0 = time.perf_counter()
        # 1. Load Agent
        agent = session.get(Agent, request.agent_id)
        if not agent or int(agent.tenant_id or 0) != int(auth.tenant.id):
            raise HTTPException(status_code=404, detail="Agent not found")

        # 1.5 Create or Retrieve Chat Session
        chat_session = session.exec(
            select(ChatSession)
            .where(
                ChatSession.agent_id == agent.id,
                ChatSession.tenant_id == auth.tenant.id,
            )
            .order_by(ChatSession.created_at.desc())
        ).first()
        if not chat_session:
            chat_session = ChatSession(agent_id=agent.id, tenant_id=auth.tenant.id)
            session.add(chat_session)
            session.commit()
            session.refresh(chat_session)

        # 2. Knowledge files are now handled by a dedicated MCP. No direct injection.
        composed = compose_conversation_prompt(
            registry=get_default_conversation_skill_registry(),
            base_prompt=agent.system_prompt,
            task_kind=ConversationTaskKind.CONVERSATION,
            channel="chat",
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
        )
        final_system_prompt = composed.system_prompt
        logger.info(
            "chat conversation skills: agent_id=%s applied=%s",
            agent.id,
            [item.get("id") for item in composed.applied_skills],
        )

        # 3. Load Linked MCP Servers
        links = session.exec(select(AgentMCPServer).where(AgentMCPServer.agent_id == agent.id)).all()
        mcp_server_ids = [link.mcp_server_id for link in links]
        
        # 4. Fetch Tools and Build Map
        tools = []
        tool_map = {} 
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scripts_dir = os.getenv("MCP_SCRIPTS_DIR", os.path.join(base_dir, "mcp-runtime-scripts"))

        t_tools0 = time.perf_counter()
        # IMPORTANT: SQLModel Session is sync and not safe to share across concurrent tasks.
        # Load MCP configs sequentially, then list tools concurrently (no DB access).
        server_ids_for_tools: List[int] = []
        for server_id in mcp_server_ids:
            try:
                mcp_server_db = session.get(MCPServer, server_id)
                if not mcp_server_db:
                    continue

                if str(mcp_server_db.script or "").strip() == "calendar_mcp.py" and not bool(agent.calendar_enabled):
                    continue

                status = await mcp_manager.get_mcp_status(str(server_id))
                if status.get("status") == "not found":
                    env_vars = {}
                    if mcp_server_db.env_vars:
                        try:
                            env_vars = json.loads(mcp_server_db.env_vars)
                        except Exception:
                            env_vars = {}

                    args = []
                    if mcp_server_db.args:
                        try:
                            args = json.loads(mcp_server_db.args)
                        except Exception:
                            args = []

                    if not args and mcp_server_db.command == "python":
                        full_script_path = os.path.join(scripts_dir, mcp_server_db.script)
                        args = [full_script_path]

                    await mcp_manager.spawn_mcp(
                        str(server_id),
                        mcp_server_db.command,
                        args,
                        cwd=mcp_server_db.cwd,
                        env=env_vars,
                    )

                server_ids_for_tools.append(server_id)
            except Exception as e:
                logger.warning(f"Error preparing MCP server {server_id}: {e}")

        tool_lists = await asyncio.gather(
            *[mcp_manager.list_mcp_tools(str(server_id)) for server_id in server_ids_for_tools],
            return_exceptions=True,
        )
        t_tools1 = time.perf_counter()
        if mcp_server_ids:
            logger.info(
                "chat tools load: agent_id=%s servers=%s dt=%.3fs",
                agent.id,
                len(mcp_server_ids),
                (t_tools1 - t_tools0),
            )

        for server_id, server_tools in zip(server_ids_for_tools, tool_lists):
            if isinstance(server_tools, Exception):
                logger.warning("Error listing tools from server %s: %s", server_id, server_tools)
                continue
            for tool in server_tools:
                tool_def = tool.model_dump(exclude_none=True)
                openai_tool = _sanitize_chat_tool(tool_def)
                tools.append(openai_tool)
                tool_map[tool_def["name"]] = str(server_id)

        if any(_is_calendar_tool(tool_name) for tool_name in tool_map):
            final_system_prompt = f"{final_system_prompt}\n\n{CALENDAR_TOOL_RULES}"

        # 5. Build Chat History
        messages = [{"role": "system", "content": final_system_prompt}]
        
        # Fetch recent messages from DB for context (limit to last 20)
        t_hist0 = time.perf_counter()
        db_messages = session.exec(
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == chat_session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(20)
        ).all()
        db_messages.reverse()
        t_hist1 = time.perf_counter()
        logger.info(
            "chat history load: agent_id=%s session_id=%s msgs=%s dt=%.3fs",
            agent.id,
            chat_session.id,
            len(db_messages),
            (t_hist1 - t_hist0),
        )

        for msg in db_messages:
            if msg.role == "user":
                messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                assistant_msg = {"role": "assistant", "content": msg.content}
                if msg.tool_calls:
                    try:
                        # Deserialize tool calls
                        tool_calls_data = json.loads(msg.tool_calls)
                        # Convert to object format if needed, but dict is fine for OpenAI client
                        assistant_msg["tool_calls"] = tool_calls_data
                    except:
                        pass
                messages.append(assistant_msg)
            elif msg.role == "tool":
                tool_msg = {
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id
                }
                messages.append(tool_msg)

        # Append Current User Message
        messages.append({"role": "user", "content": request.message})
        save_message(session, chat_session.id, "user", request.message, tenant_id=auth.tenant.id)

        # 6. Chat Loop
        max_turns = 5
        require_calendar_tool_first = (
            bool(tools)
            and any(_is_calendar_tool(tool_name) for tool_name in tool_map)
            and _is_scheduling_request(request.message)
        )
        for turn_idx in range(max_turns):
            try:
                t_llm0 = time.perf_counter()
                task = LLMTask.TOOL_USE if tools else LLMTask.CONVERSATION
                execute_kwargs: Dict[str, Any] = {}
                if tools:
                    execute_kwargs["tools"] = tools
                if require_calendar_tool_first and turn_idx == 0:
                    execute_kwargs["tool_choice"] = "required"
                response = await llm_router.execute(
                    task=task,
                    messages=messages,
                    **execute_kwargs,
                )
                t_llm1 = time.perf_counter()
                logger.info(
                    "chat llm call: agent_id=%s routing=platform tool_mode=%s dt=%.3fs",
                    agent.id,
                    bool(tools),
                    (t_llm1 - t_llm0),
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"LLM Error: {str(e)}")

            # Append assistant message to history object (LLMMessage format)
            assistant_msg = LLMMessage(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls
            )
            messages.append(assistant_msg)

            # Save Assistant Message (Content + Tool Calls)
            tool_calls_list = response.tool_calls
            
            # Save to DB even if content is None (if tool calls exist)
            if response.content or tool_calls_list:
                save_message(session, chat_session.id, "assistant", response.content, tenant_id=auth.tenant.id, tool_calls=tool_calls_list)

            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["function"]["name"]
                    tool_args_str = tool_call["function"]["arguments"]
                    
                    content_str = "Error executing tool"
                    if tool_name in tool_map:
                        server_id = tool_map[tool_name]
                        try:
                            tool_args = json.loads(tool_args_str)
                            if not isinstance(tool_args, dict):
                                tool_args = {}
                            tool_args = _inject_authenticated_tool_args(
                                tool_name,
                                tool_args,
                                auth=auth,
                                agent=agent,
                            )
                            t_tool0 = time.perf_counter()
                            result = await mcp_manager.call_mcp_tool(server_id, tool_name, tool_args)
                            t_tool1 = time.perf_counter()
                            logger.info(
                                "chat tool call: agent_id=%s mcp_id=%s tool=%s dt=%.3fs",
                                agent.id,
                                server_id,
                                tool_name,
                                (t_tool1 - t_tool0),
                            )
                            
                            content_str = str(result)
                            if isinstance(result, list):
                                content_str = "\n".join([c.text for c in result if c.type == 'text'])
                            elif hasattr(result, 'content') and isinstance(result.content, list):
                                content_str = "\n".join([c.text for c in result.content if c.type == 'text'])
                        except Exception as e:
                            content_str = f"Error executing tool: {str(e)}"
                    else:
                        content_str = "Tool not found"

                    # Append Tool Result to messages list
                    messages.append(LLMMessage(
                        role="tool",
                        tool_call_id=tool_call["id"],
                        content=content_str
                    ))
                    # Save Tool Result to DB
                    save_message(session, chat_session.id, "tool", content_str, tenant_id=auth.tenant.id, tool_call_id=tool_call["id"])
            else:
                t1 = time.perf_counter()
                logger.info("chat total: agent_id=%s dt=%.3fs", agent.id, (t1 - t0))
                return ChatResponse(response=response.content or "")
                
        return ChatResponse(response="Max chat turns reached.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Chat endpoint error")
        raise HTTPException(status_code=500, detail=f"Internal Error: {str(e)}")

@router.get("/conversations")
def list_conversations(session: Session = Depends(get_session)):
    """List all active chat sessions with the latest message snippet."""
    from models import ChatSession, ChatMessage, Lead
    sessions = session.exec(select(ChatSession).order_by(ChatSession.updated_at.desc())).all()
    results = []
    for s in sessions:
        last_msg = session.exec(
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == s.id)
            .order_by(ChatMessage.created_at.desc())
        ).first()
        
        # Try to find a lead associated with this agent/workspace if possible
        # For MVP, we'll just return the session data
        results.append({
            "id": s.id,
            "agent_id": s.agent_id,
            "last_message": last_msg.content if last_msg else "No messages",
            "updated_at": s.updated_at,
            "created_at": s.created_at
        })
    return results

@router.get("/{session_id}/messages", response_model=List[ChatMessage])
def get_session_messages(session_id: int, session: Session = Depends(get_session)):
    """Return the message history for a specific chat session."""
    from models import ChatMessage
    return session.exec(
        select(ChatMessage)
        .where(ChatMessage.chat_session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    ).all()
