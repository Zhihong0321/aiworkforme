from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session, select
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import json
from pydantic import BaseModel

from src.infra.database import get_session
from src.adapters.api.dependencies import require_tenant_access, AuthContext, get_llm_router
from src.adapters.db.agent_models import Agent, AgentMCPServer, AgentKnowledgeFile, AgentRead, AgentUpdate
from src.adapters.db.mcp_models import MCPServer
from src.app.runtime.knowledge_processor import KnowledgeProcessor
from src.infra.llm.router import LLMRouter
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["Agent Management"])


class AgentCreate(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    mimic_human_typing: Optional[bool] = False
    emoji_level: Optional[str] = "none"
    segment_delay_ms: Optional[int] = 800

@router.get("/", response_model=List[AgentRead])
def list_agents(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    import traceback
    try:
        agents = session.exec(select(Agent).where(Agent.tenant_id == auth.tenant.id)).all()
        results: List[AgentRead] = []

        for agent in agents:
            linked_ids = [
                link_id
                for link_id in session.exec(
                    select(AgentMCPServer.mcp_server_id).where(AgentMCPServer.agent_id == agent.id)
                ).all()
                if link_id is not None
            ]

            # Use model_dump in Pydantic v2 or dict in v1
            agent_data = agent.model_dump(
                exclude={"chat_sessions", "mcp_servers", "knowledge_files", "model", "reasoning_enabled"}
            )
            results.append(
                AgentRead(
                    **agent_data,
                    linked_mcp_ids=linked_ids,
                    linked_mcp_count=len(linked_ids)
                )
            )

        return results
    except Exception as e:
        logger.error(f"LIST AGENTS ERROR: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=AgentRead)
def create_agent(
    agent_in: AgentCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    name = (agent_in.name or "").strip() or "New Agent"
    system_prompt = (agent_in.system_prompt or "").strip()

    new_agent = Agent(
        name=name,
        system_prompt=system_prompt,
        tenant_id=auth.tenant.id,
        created_at=datetime.utcnow(),
        mimic_human_typing=bool(agent_in.mimic_human_typing or False),
        emoji_level=str(agent_in.emoji_level or "none"),
        segment_delay_ms=int(agent_in.segment_delay_ms or 800),
    )
    
    session.add(new_agent)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Invalid agent payload") from exc
    except Exception:
        session.rollback()
        logger.exception("CREATE AGENT ERROR")
        raise HTTPException(status_code=500, detail="Failed to create agent")
    session.refresh(new_agent)
    
    return AgentRead(
        id=new_agent.id,
        name=new_agent.name,
        system_prompt=new_agent.system_prompt,
        linked_mcp_ids=[],
        linked_mcp_count=0,
        mimic_human_typing=new_agent.mimic_human_typing,
        emoji_level=new_agent.emoji_level,
        segment_delay_ms=new_agent.segment_delay_ms,
    )

@router.put("/{agent_id}", response_model=AgentRead)
def update_agent(
    agent_id: int, 
    payload: AgentUpdate, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")

    if payload.name is not None:
        agent.name = payload.name
    if payload.system_prompt is not None:
        agent.system_prompt = payload.system_prompt
    if payload.mimic_human_typing is not None:
        agent.mimic_human_typing = payload.mimic_human_typing
    if payload.emoji_level is not None:
        agent.emoji_level = payload.emoji_level
    if payload.segment_delay_ms is not None:
        agent.segment_delay_ms = payload.segment_delay_ms

    session.add(agent)
    session.commit()
    session.refresh(agent)
    linked_ids = session.exec(
        select(AgentMCPServer.mcp_server_id).where(AgentMCPServer.agent_id == agent.id)
    ).all()
    return AgentRead(
        **agent.model_dump(
            exclude={"chat_sessions", "mcp_servers", "knowledge_files", "model", "reasoning_enabled"}
        ),
        linked_mcp_ids=list(linked_ids),
        linked_mcp_count=len(linked_ids),
    )

@router.get("/{agent_id}", response_model=AgentRead)
def get_agent(
    agent_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    linked_ids = session.exec(
        select(AgentMCPServer.mcp_server_id).where(AgentMCPServer.agent_id == agent.id)
    ).all()

    return AgentRead(
        **agent.model_dump(
            exclude={"chat_sessions", "mcp_servers", "knowledge_files", "model", "reasoning_enabled"}
        ),
        linked_mcp_ids=list(linked_ids),
        linked_mcp_count=len(linked_ids)
    )

@router.delete("/{agent_id}")
def delete_agent(
    agent_id: int, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")

    session.delete(agent)
    session.commit()
    return {"message": "Agent deleted"}

@router.post("/{agent_id}/link-mcp/{server_id}")
def link_mcp_to_agent(
    agent_id: int, 
    server_id: int, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    server = session.get(MCPServer, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found")

    existing_link = session.get(AgentMCPServer, (agent_id, server_id))
    if existing_link:
        return {"message": "MCP already linked to agent"}

    link = AgentMCPServer(agent_id=agent_id, mcp_server_id=server_id)
    session.add(link)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return {"message": "MCP already linked to agent"}

    return {"message": "Linked successfully"}

@router.post("/{agent_id}/knowledge")
async def upload_agent_knowledge(
    agent_id: int,
    file: UploadFile = File(...),
    tags: Optional[str] = Form(default="[]"),
    description: Optional[str] = Form(default=""),
    session: Session = Depends(get_session),
    llm: LLMRouter = Depends(get_llm_router),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")

    content_bytes = await file.read()
    content_str = ""
    
    if file.content_type.startswith("image/"):
        processor = KnowledgeProcessor(session, llm)
        content_str = await processor.process_image(content_bytes, file.filename)
    elif file.content_type == "application/pdf":
        processor = KnowledgeProcessor(session, llm)
        content_str = await processor.process_pdf(content_bytes, file.filename)
    else:
        try:
            content_str = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
             raise HTTPException(status_code=400, detail="Text file must be valid UTF-8")

    knowledge = AgentKnowledgeFile(
        agent_id=agent_id,
        tenant_id=auth.tenant.id,
        filename=file.filename,
        content=content_str,
        tags=tags,
        description=description,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(knowledge)
    session.commit()
    session.refresh(knowledge)
    return knowledge

@router.get("/{agent_id}/knowledge", response_model=List[AgentKnowledgeFile])
def list_agent_knowledge(
    agent_id: int, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    files = session.exec(select(AgentKnowledgeFile).where(AgentKnowledgeFile.agent_id == agent_id)).all()
    return files

@router.delete("/{agent_id}/knowledge/{file_id}")
def delete_agent_knowledge(
    agent_id: int, 
    file_id: int, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    file = session.get(AgentKnowledgeFile, file_id)
    if not file or file.agent_id != agent_id or file.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="File not found or access denied")
    
    session.delete(file)
    session.commit()
    return {"message": "File deleted"}
