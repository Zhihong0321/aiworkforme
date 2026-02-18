"""
MODULE: Application Background Tasks - Inbound Worker
PURPOSE: Process inbound messages through the real AI agent pipeline.
         Each inbound message is handled by ConversationAgentRuntime, which
         uses the assigned agent's system_prompt, RAG knowledge, lead memory,
         and MCP tools — exactly the same pipeline as the Playground.
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import uuid4

from sqlmodel import Session, select

from src.infra.database import engine
from src.adapters.api.dependencies import llm_router
from src.adapters.db.messaging_models import UnifiedMessage, UnifiedThread, OutboundQueue, ThreadInsight
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.agent_models import Agent
from src.app.runtime.agent_runtime import ConversationAgentRuntime

logger = logging.getLogger(__name__)


INBOUND_POLL_SECONDS = float(os.getenv("MESSAGING_INBOUND_POLL_SECONDS", "2"))
INBOUND_BATCH_SIZE = int(os.getenv("MESSAGING_INBOUND_BATCH_SIZE", "5"))


# ---------------------------------------------------------------------------
# Thread / Agent resolution
# ---------------------------------------------------------------------------

def _resolve_thread_agent(session: Session, message: UnifiedMessage) -> Optional[Agent]:
    """
    Find the Agent assigned to this thread.
    If none is assigned yet, pick one from the lead's workspace (or the first
    agent in the tenant) and persist it on the thread for future messages.
    """
    if not message.thread_id:
        return None

    thread = session.get(UnifiedThread, message.thread_id)
    if not thread or thread.tenant_id != message.tenant_id:
        return None

    if thread.agent_id is None:
        lead = session.get(Lead, message.lead_id)
        if not lead or lead.tenant_id != message.tenant_id:
            return None

        workspace = session.get(Workspace, lead.workspace_id)
        candidate_agent_id = (
            workspace.agent_id
            if workspace and workspace.tenant_id == message.tenant_id
            else None
        )
        if candidate_agent_id is None:
            fallback = session.exec(
                select(Agent)
                .where(Agent.tenant_id == message.tenant_id)
                .order_by(Agent.id.asc())
            ).first()
            candidate_agent_id = fallback.id if fallback else None

        if candidate_agent_id is None:
            logger.warning(
                "No agent found for tenant_id=%s, message_id=%s — marking human_takeover",
                message.tenant_id, message.id,
            )
            return None

        thread.agent_id = candidate_agent_id
        thread.updated_at = datetime.utcnow()
        session.add(thread)
        session.commit()
        session.refresh(thread)

    agent = session.get(Agent, thread.agent_id)
    if not agent or agent.tenant_id != message.tenant_id:
        return None
    return agent


# ---------------------------------------------------------------------------
# History builder — reads from et_messages (UnifiedMessage), NOT ChatMessageNew
# ---------------------------------------------------------------------------

def _build_thread_history(session: Session, message: UnifiedMessage) -> List[Dict[str, str]]:
    """
    Return the last 12 messages in this thread as OpenAI-style role/content dicts.
    Excludes the current inbound message (it will be passed as user_message separately).
    """
    if not message.thread_id:
        return []

    items = session.exec(
        select(UnifiedMessage)
        .where(
            UnifiedMessage.tenant_id == message.tenant_id,
            UnifiedMessage.thread_id == message.thread_id,
            UnifiedMessage.id != message.id,          # exclude current message
        )
        .order_by(UnifiedMessage.created_at.desc())
        .limit(12)
    ).all()
    items.reverse()

    history: List[Dict[str, str]] = []
    for item in items:
        if not item.text_content:
            continue
        role = "user" if item.direction == "inbound" else "assistant"
        history.append({"role": role, "content": item.text_content})
    return history


# ---------------------------------------------------------------------------
# Outbound enqueue — writes reply to et_messages + et_outbound_queue
# ---------------------------------------------------------------------------

def _enqueue_outbound_reply(
    session: Session,
    inbound_message: UnifiedMessage,
    agent_id: int,
    text: str,
) -> UnifiedMessage:
    now = datetime.utcnow()
    outbound = UnifiedMessage(
        tenant_id=inbound_message.tenant_id,
        lead_id=inbound_message.lead_id,
        thread_id=inbound_message.thread_id,
        channel_session_id=inbound_message.channel_session_id,
        channel=inbound_message.channel,
        external_message_id=f"out_{uuid4().hex}",
        direction="outbound",
        message_type="text",
        text_content=text,
        raw_payload={
            "source": "ai_agent",
            "inbound_message_id": inbound_message.id,
            "agent_id": agent_id,
        },
        delivery_status="queued",
        created_at=now,
        updated_at=now,
    )
    session.add(outbound)
    session.commit()
    session.refresh(outbound)

    queue = OutboundQueue(
        tenant_id=inbound_message.tenant_id,
        message_id=outbound.id,
        channel=inbound_message.channel,
        channel_session_id=inbound_message.channel_session_id,
        status="queued",
        retry_count=0,
        next_attempt_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(queue)
    session.commit()
    return outbound


# ---------------------------------------------------------------------------
# Core processor — one inbound message through the real AI agent pipeline
# ---------------------------------------------------------------------------

async def _process_one_inbound(session: Session, message: UnifiedMessage):
    # Mark as in-progress immediately so the batch loop doesn't re-pick it
    message.delivery_status = "inbound_processing"
    message.updated_at = datetime.utcnow()
    session.add(message)
    session.commit()
    session.refresh(message)

    # 1. Resolve which agent handles this thread
    agent = _resolve_thread_agent(session, message)
    if not agent:
        message.delivery_status = "inbound_human_takeover"
        message.updated_at = datetime.utcnow()
        session.add(message)
        session.commit()
        return

    # 2. Resolve workspace_id from the lead (required by ConversationAgentRuntime)
    lead = session.get(Lead, message.lead_id)
    if not lead or not lead.workspace_id:
        logger.error(
            "Cannot process inbound message_id=%s: lead %s has no workspace_id",
            message.id, message.lead_id,
        )
        message.delivery_status = "inbound_error"
        message.updated_at = datetime.utcnow()
        session.add(message)
        session.commit()
        return

    # 3. Build conversation history from et_messages (the real message store)
    history = _build_thread_history(session, message)

    # 4. Run the REAL AI agent pipeline
    #    - Uses agent.system_prompt
    #    - Runs RAG over agent's knowledge files
    #    - Loads lead memory
    #    - Respects policy / risk checks
    #    - history_override bypasses ChatMessageNew so we stay in et_messages
    logger.info(
        "Running AI agent (id=%s, name=%s) for inbound message_id=%s (lead=%s)",
        agent.id, agent.name, message.id, message.lead_id,
    )
    runtime = ConversationAgentRuntime(session, llm_router)
    result = await runtime.run_turn(
        lead_id=message.lead_id,
        workspace_id=lead.workspace_id,
        user_message=message.text_content or "",
        agent_id_override=agent.id,
        bypass_safety=False,
        history_override=history,
    )

    # 5. Handle the result
    status = result.get("status")

    if status == "sent":
        reply_text = result["content"]
        _enqueue_outbound_reply(session, message, agent.id, reply_text)
        message.delivery_status = "inbound_ai_replied"
        logger.info(
            "AI reply enqueued for message_id=%s: %.80s…", message.id, reply_text
        )

    elif status == "blocked":
        reason = result.get("reason", "unknown")
        logger.warning(
            "AI reply blocked by policy for message_id=%s: %s", message.id, reason
        )
        message.delivery_status = "inbound_human_takeover"

    else:
        # status == "error" or anything unexpected — raise so outer handler logs it
        raise RuntimeError(
            f"ConversationAgentRuntime returned unexpected status '{status}' "
            f"for message_id={message.id}: {result}"
        )

    message.updated_at = datetime.utcnow()
    session.add(message)
    session.commit()


# ---------------------------------------------------------------------------
# Background worker loop
# ---------------------------------------------------------------------------

async def background_inbound_worker_loop():
    logger.info(
        "Starting inbound worker loop (poll=%ss, batch=%s)",
        INBOUND_POLL_SECONDS,
        INBOUND_BATCH_SIZE,
    )
    while True:
        processed = 0
        try:
            with Session(engine) as session:
                inbound_batch = session.exec(
                    select(UnifiedMessage)
                    .where(
                        UnifiedMessage.direction == "inbound",
                        UnifiedMessage.delivery_status == "received",
                        UnifiedMessage.thread_id != None,
                    )
                    .order_by(UnifiedMessage.created_at.asc(), UnifiedMessage.id.asc())
                    .limit(INBOUND_BATCH_SIZE)
                ).all()

                for inbound in inbound_batch:
                    try:
                        await _process_one_inbound(session, inbound)
                        processed += 1
                    except Exception as exc:
                        logger.exception(
                            "Inbound processing error for message_id=%s: %s",
                            inbound.id, exc,
                        )
                        session.rollback()
                        db_inbound = session.get(UnifiedMessage, inbound.id)
                        if db_inbound:
                            db_inbound.delivery_status = "inbound_error"
                            db_inbound.updated_at = datetime.utcnow()
                            session.add(db_inbound)
                            session.commit()

        except Exception as exc:
            logger.exception("Inbound worker loop error: %s", exc)

        if processed == 0:
            await asyncio.sleep(INBOUND_POLL_SECONDS)
        else:
            await asyncio.sleep(0)
