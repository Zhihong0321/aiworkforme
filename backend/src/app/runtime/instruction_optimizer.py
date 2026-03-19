from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from src.adapters.db.agent_models import (
    Agent,
    AgentKnowledgeFile,
    AgentMCPServer,
    AgentSalesMaterial,
)
from src.adapters.db.mcp_models import MCPServer
from src.adapters.db.messaging_models import UnifiedMessage, UnifiedThread
from src.app.conversation_skills import (
    ConversationTaskKind,
    compose_conversation_prompt,
    get_default_conversation_skill_registry,
)
from src.infra.llm.router import LLMRouter
from src.infra.llm.schemas import LLMTask

INSTRUCTION_OPTIMIZER_MODEL = "gemini-3.1-flash-lite-preview"
MAX_PASTED_HISTORY_CHARS = 12000
MAX_CONTEXT_MESSAGES = 40


def _trim_text(value: Optional[str], limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}\n...[truncated]"


def _safe_json_object(raw: str) -> Dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _lines_from_pasted_history(chat_history: Optional[str]) -> str:
    return _trim_text(chat_history, MAX_PASTED_HISTORY_CHARS)


def _lines_from_thread(thread_messages: list[UnifiedMessage]) -> str:
    lines: list[str] = []
    for item in thread_messages:
        role = "customer" if item.direction == "inbound" else "agent"
        body = (item.text_content or "").strip()
        if item.media_url:
            media_note = f"(media: {item.message_type} {item.media_url})"
            body = f"{body}\n{media_note}".strip() if body else media_note
        if not body:
            body = "(empty message)"
        lines.append(f"[{role} | {item.created_at.isoformat()}] {body}")
    return _trim_text("\n".join(lines), MAX_PASTED_HISTORY_CHARS)


def _knowledge_manifest(session: Session, tenant_id: int, agent_id: int) -> str:
    files = session.exec(
        select(AgentKnowledgeFile)
        .where(
            AgentKnowledgeFile.tenant_id == tenant_id,
            AgentKnowledgeFile.agent_id == agent_id,
        )
        .order_by(AgentKnowledgeFile.updated_at.desc())
        .limit(12)
    ).all()
    if not files:
        return "None."

    lines = []
    for item in files:
        tags = str(item.tags or "[]")
        description = _trim_text(item.description, 240) or "No description."
        lines.append(f"- {item.filename}: {description} | tags={tags}")
    return "\n".join(lines)


def _sales_material_manifest(session: Session, tenant_id: int, agent_id: int) -> str:
    materials = session.exec(
        select(AgentSalesMaterial)
        .where(
            AgentSalesMaterial.tenant_id == tenant_id,
            AgentSalesMaterial.agent_id == agent_id,
        )
        .order_by(AgentSalesMaterial.updated_at.desc())
        .limit(12)
    ).all()
    if not materials:
        return "None."

    lines = []
    for item in materials:
        description = _trim_text(item.description, 240) or "No description."
        lines.append(f"- {item.filename} ({item.kind if hasattr(item, 'kind') else item.media_type}): {description}")
    return "\n".join(lines)


def _linked_skill_manifest(session: Session, tenant_id: int, agent_id: int) -> str:
    rows = session.exec(
        select(MCPServer)
        .join(AgentMCPServer, AgentMCPServer.mcp_server_id == MCPServer.id)
        .where(
            AgentMCPServer.agent_id == agent_id,
            MCPServer.tenant_id == tenant_id,
        )
        .order_by(MCPServer.name.asc())
    ).all()
    if not rows:
        return "None."

    lines = []
    for server in rows:
        description = _trim_text(server.description if hasattr(server, "description") else "", 180) or "No description."
        lines.append(f"- {server.name}: {description}")
    return "\n".join(lines)


def _build_optimizer_prompt(
    *,
    agent: Agent,
    feedback: str,
    context_source: str,
    conversation_history: str,
    effective_prompt: str,
    applied_skills: list[dict[str, Any]],
    linked_skills: str,
    knowledge_manifest: str,
    sales_material_manifest: str,
) -> list[dict[str, str]]:
    applied_skill_ids = ", ".join(item.get("id", "") for item in applied_skills if item.get("id")) or "None"
    system_message = (
        "You are an internal prompt and instruction optimizer for an AI agent platform. "
        "Your job is to improve the agent's system instructions after bad chat performance. "
        "Return strict JSON only with keys: "
        "summary, diagnosis, instruction_changes, knowledge_updates, warnings, optimized_system_prompt. "
        "diagnosis, instruction_changes, knowledge_updates, and warnings must each be arrays of short strings. "
        "optimized_system_prompt must be a complete replacement prompt ready to paste into the agent's system_prompt field. "
        "Preserve the agent's role and business intent, but make the instructions clearer, more operational, and more resilient. "
        "Do not mention this optimizer, hidden analysis, or that the prompt was rewritten."
    )
    user_message = (
        f"AGENT NAME:\n{agent.name}\n\n"
        f"BEHAVIOR SETTINGS:\n"
        f"- mimic_human_typing: {bool(agent.mimic_human_typing)}\n"
        f"- emoji_level: {agent.emoji_level}\n"
        f"- segment_delay_ms: {agent.segment_delay_ms}\n\n"
        f"USER FEEDBACK ABOUT BAD PERFORMANCE:\n{_trim_text(feedback, 4000)}\n\n"
        f"CURRENT RAW SYSTEM PROMPT:\n{agent.system_prompt or '(empty)'}\n\n"
        f"EFFECTIVE COMPOSED SYSTEM PROMPT SENT TO THE MODEL:\n{effective_prompt or '(empty)'}\n\n"
        f"APPLIED PLATFORM CONVERSATION SKILLS:\n{applied_skill_ids}\n\n"
        f"LINKED MCP / TOOLING:\n{linked_skills}\n\n"
        f"KNOWLEDGE FILE MANIFEST:\n{knowledge_manifest}\n\n"
        f"SALES MATERIAL MANIFEST:\n{sales_material_manifest}\n\n"
        f"PROBLEM CONTEXT SOURCE:\n{context_source}\n\n"
        f"PROBLEMATIC CHAT HISTORY:\n{conversation_history or 'None provided.'}\n\n"
        "OUTPUT REQUIREMENTS:\n"
        "- Focus first on why performance was weak.\n"
        "- Only use knowledge_updates for facts, SOPs, examples, or documents that should live outside the prompt.\n"
        "- Keep optimized_system_prompt concise enough to be maintained by humans.\n"
        "- If evidence is weak, say so in warnings but still produce the best possible rewritten prompt."
    )
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]


async def optimize_agent_instruction(
    *,
    session: Session,
    llm_router: LLMRouter,
    tenant_id: int,
    agent: Agent,
    feedback: str,
    chat_history: Optional[str] = None,
    thread_id: Optional[int] = None,
    max_thread_messages: int = 20,
) -> Dict[str, Any]:
    selected_thread_id: Optional[int] = None
    context_source = "agent_only"
    conversation_history = _lines_from_pasted_history(chat_history)
    channel = "chat"

    if thread_id is not None:
        thread = session.get(UnifiedThread, thread_id)
        if (
            not thread
            or thread.tenant_id != tenant_id
            or int(thread.agent_id or 0) != int(agent.id)
        ):
            raise HTTPException(status_code=404, detail="Thread not found for this agent")
        safe_limit = min(max(int(max_thread_messages or 20), 1), MAX_CONTEXT_MESSAGES)
        thread_messages = session.exec(
            select(UnifiedMessage)
            .where(
                UnifiedMessage.tenant_id == tenant_id,
                UnifiedMessage.thread_id == thread.id,
            )
            .order_by(UnifiedMessage.created_at.desc(), UnifiedMessage.id.desc())
            .limit(safe_limit)
        ).all()
        thread_messages.reverse()
        conversation_history = _lines_from_thread(thread_messages)
        context_source = "stored_thread"
        selected_thread_id = thread.id
        channel = thread.channel or channel
    elif conversation_history:
        context_source = "pasted_history"

    composed = compose_conversation_prompt(
        registry=get_default_conversation_skill_registry(),
        base_prompt=agent.system_prompt,
        task_kind=ConversationTaskKind.CONVERSATION,
        channel=channel,
        agent_id=agent.id,
        tenant_id=tenant_id,
    )

    messages = _build_optimizer_prompt(
        agent=agent,
        feedback=feedback,
        context_source=context_source,
        conversation_history=conversation_history,
        effective_prompt=composed.system_prompt,
        applied_skills=composed.applied_skills,
        linked_skills=_linked_skill_manifest(session, tenant_id, int(agent.id)),
        knowledge_manifest=_knowledge_manifest(session, tenant_id, int(agent.id)),
        sales_material_manifest=_sales_material_manifest(session, tenant_id, int(agent.id)),
    )
    response = await llm_router.execute(
        task=LLMTask.REASONING,
        messages=messages,
        temperature=0.2,
        max_tokens=1800,
        response_format={"type": "json_object"},
        provider="uniapi",
        model=INSTRUCTION_OPTIMIZER_MODEL,
        uniapi_schema="gemini_native",
        disable_fallback=True,
    )
    parsed = _safe_json_object(response.content or "")
    optimized_prompt = str(parsed.get("optimized_system_prompt") or "").strip()
    if not optimized_prompt:
        raise HTTPException(status_code=502, detail="Instruction optimizer returned no optimized_system_prompt")

    provider_info = response.provider_info or {}
    return {
        "agent_id": int(agent.id),
        "context_source": context_source,
        "used_thread_id": selected_thread_id,
        "provider": str(provider_info.get("provider") or "uniapi"),
        "model": str(provider_info.get("model") or INSTRUCTION_OPTIMIZER_MODEL),
        "summary": str(parsed.get("summary") or "").strip() or "Optimizer completed.",
        "diagnosis": [str(item).strip() for item in parsed.get("diagnosis") or [] if str(item).strip()],
        "instruction_changes": [
            str(item).strip()
            for item in parsed.get("instruction_changes") or []
            if str(item).strip()
        ],
        "knowledge_updates": [
            str(item).strip()
            for item in parsed.get("knowledge_updates") or []
            if str(item).strip()
        ],
        "warnings": [str(item).strip() for item in parsed.get("warnings") or [] if str(item).strip()],
        "optimized_system_prompt": optimized_prompt,
    }
