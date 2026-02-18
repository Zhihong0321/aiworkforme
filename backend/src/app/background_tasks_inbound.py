"""
MODULE: Application Background Tasks - Inbound Worker
PURPOSE: Process inbound messages with thread-bound AI agent decisions.
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import uuid4

from sqlmodel import Session, select

from src.infra.database import engine
from src.adapters.api.dependencies import llm_router
from src.infra.llm.schemas import LLMTask
from src.adapters.db.messaging_models import UnifiedMessage, UnifiedThread, OutboundQueue, ThreadInsight
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.agent_models import Agent

logger = logging.getLogger(__name__)


INBOUND_POLL_SECONDS = float(os.getenv("MESSAGING_INBOUND_POLL_SECONDS", "2"))
INBOUND_BATCH_SIZE = int(os.getenv("MESSAGING_INBOUND_BATCH_SIZE", "5"))


def _resolve_thread_agent(session: Session, message: UnifiedMessage) -> Optional[Agent]:
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
        candidate_agent_id = workspace.agent_id if workspace and workspace.tenant_id == message.tenant_id else None
        if candidate_agent_id is None:
            fallback = session.exec(
                select(Agent)
                .where(Agent.tenant_id == message.tenant_id)
                .order_by(Agent.id.asc())
            ).first()
            candidate_agent_id = fallback.id if fallback else None

        if candidate_agent_id is None:
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


def _build_thread_history(session: Session, message: UnifiedMessage) -> List[Dict[str, str]]:
    if not message.thread_id:
        return []
    items = session.exec(
        select(UnifiedMessage)
        .where(
            UnifiedMessage.tenant_id == message.tenant_id,
            UnifiedMessage.thread_id == message.thread_id,
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


async def _decide_action_and_reply(agent: Agent, history: List[Dict[str, str]]) -> Dict[str, Any]:
    system_prompt = (
        f"{agent.system_prompt}\n\n"
        "You are deciding inbound handling. Return strict JSON only with keys: "
        "action, reply_text, summary, label. "
        "action must be one of: auto_reply, follow_up, human_takeover."
    )
    if not history:
        history = [{"role": "user", "content": "No inbound content available."}]

    try:
        response = await llm_router.execute(
            task=LLMTask.EXTRACTION,
            messages=[{"role": "system", "content": system_prompt}] + history,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except Exception as exc:
        logger.warning("Inbound decision LLM failed, using fallback auto reply: %s", exc)
        return {
            "action": "auto_reply",
            "reply_text": "Thanks for your message. I got it and will help you shortly.",
            "summary": "fallback due to llm error",
            "label": "fallback_auto_reply",
        }

    raw = (response.content or "").strip()
    if not raw:
        return {"action": "human_takeover", "reply_text": "", "summary": "", "label": "unknown"}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"action": "human_takeover", "reply_text": "", "summary": raw[:500], "label": "parse_error"}

    action = str(data.get("action", "human_takeover")).strip().lower()
    if action not in {"auto_reply", "follow_up", "human_takeover"}:
        action = "human_takeover"
    return {
        "action": action,
        "reply_text": str(data.get("reply_text") or "").strip(),
        "summary": str(data.get("summary") or "").strip(),
        "label": str(data.get("label") or action).strip()[:64],
    }


def _persist_thread_insight(
    session: Session,
    message: UnifiedMessage,
    action: str,
    summary: str,
    label: str,
):
    if not message.thread_id:
        return
    insight = session.exec(
        select(ThreadInsight).where(
            ThreadInsight.tenant_id == message.tenant_id,
            ThreadInsight.thread_id == message.thread_id,
        )
    ).first()
    now = datetime.utcnow()
    if not insight:
        insight = ThreadInsight(
            tenant_id=message.tenant_id,
            thread_id=message.thread_id,
            lead_id=message.lead_id,
            label=label or action,
            next_step=action,
            summary=summary or None,
            updated_at=now,
        )
    else:
        insight.label = label or action
        insight.next_step = action
        insight.summary = summary or insight.summary
        insight.updated_at = now
    session.add(insight)


def _enqueue_auto_reply(
    session: Session,
    inbound_message: UnifiedMessage,
    agent_id: int,
    text: str,
):
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
            "source": "inbound_worker",
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


async def _process_one_inbound(session: Session, message: UnifiedMessage):
    message.delivery_status = "inbound_processing"
    message.updated_at = datetime.utcnow()
    session.add(message)
    session.commit()
    session.refresh(message)

    agent = _resolve_thread_agent(session, message)
    if not agent:
        message.delivery_status = "inbound_human_takeover"
        message.updated_at = datetime.utcnow()
        session.add(message)
        session.commit()
        return

    history = _build_thread_history(session, message)
    decision = await _decide_action_and_reply(agent, history)
    action = decision["action"]

    _persist_thread_insight(
        session=session,
        message=message,
        action=action,
        summary=decision["summary"],
        label=decision["label"],
    )

    if action == "auto_reply" and decision["reply_text"]:
        _enqueue_auto_reply(session, message, agent.id, decision["reply_text"])
        message.delivery_status = "inbound_auto_reply_queued"
    elif action == "follow_up":
        message.delivery_status = "inbound_follow_up"
    else:
        message.delivery_status = "inbound_human_takeover"

    message.updated_at = datetime.utcnow()
    session.add(message)
    session.commit()


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
                        logger.exception("Inbound processing error for message_id=%s: %s", inbound.id, exc)
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
