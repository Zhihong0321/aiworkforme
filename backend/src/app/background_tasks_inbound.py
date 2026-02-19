"""
MODULE: Application Background Tasks - Inbound Worker
PURPOSE: Process inbound messages through the real AI agent pipeline.
         Each inbound message is handled by ConversationAgentRuntime, which
         uses the assigned agent's system_prompt, RAG knowledge, lead memory,
         and MCP tools — exactly the same pipeline as the Playground.
"""
import asyncio
import json
import logging
import os
import select as pyselect
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlmodel import Session, select

from src.infra.database import engine
from src.adapters.api.dependencies import llm_router
from src.adapters.db.messaging_models import UnifiedMessage, UnifiedThread, OutboundQueue
from src.adapters.db import channel_models  # must be imported before crm_models — ConversationThread.channel_session relationship
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.agent_models import Agent
from src.app.runtime.agent_runtime import ConversationAgentRuntime

logger = logging.getLogger(__name__)


INBOUND_POLL_SECONDS = float(os.getenv("MESSAGING_INBOUND_POLL_SECONDS", "2"))
INBOUND_BATCH_SIZE = int(os.getenv("MESSAGING_INBOUND_BATCH_SIZE", "5"))
INBOUND_NOTIFY_CHANNEL = os.getenv("MESSAGING_INBOUND_NOTIFY_CHANNEL", "inbound_new_message")

INBOUND_WORKER_STATE: Dict[str, Any] = {
    "started_at": None,
    "last_loop_at": None,
    "last_listen_connected_at": None,
    "last_notify_received_at": None,
    "last_notified_message_id": None,
    "last_claimed_at": None,
    "last_claimed_message_id": None,
    "last_processed_at": None,
    "last_processed_message_id": None,
    "last_error_at": None,
    "last_error_message": None,
    "notify_events_total": 0,
    "claimed_total": 0,
    "processed_total": 0,
    "errors_total": 0,
}


def _iso_now() -> str:
    return datetime.utcnow().isoformat()


def _mark_worker_state(**kwargs):
    INBOUND_WORKER_STATE.update(kwargs)


def get_inbound_worker_debug_snapshot() -> Dict[str, Any]:
    return dict(INBOUND_WORKER_STATE)


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
            UnifiedMessage.id != message.id,
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
    # Legacy fallback path: callers that do not pre-claim can still process safely.
    if message.delivery_status != "inbound_processing":
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
        bypass_safety=True,
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
        raise RuntimeError(
            f"ConversationAgentRuntime returned unexpected status '{status}' "
            f"for message_id={message.id}: {result}"
        )

    message.updated_at = datetime.utcnow()
    session.add(message)
    session.commit()


# ---------------------------------------------------------------------------
# LISTEN/NOTIFY + claim helpers
# ---------------------------------------------------------------------------

def _open_inbound_listen_connection():
    if engine.dialect.name != "postgresql":
        return None

    raw_conn = engine.raw_connection()
    raw_conn.autocommit = True
    cursor = raw_conn.cursor()
    try:
        cursor.execute(f"LISTEN {INBOUND_NOTIFY_CHANNEL};")
    finally:
        cursor.close()
    _mark_worker_state(last_listen_connected_at=_iso_now())
    logger.info("Inbound worker listening on PostgreSQL channel: %s", INBOUND_NOTIFY_CHANNEL)
    return raw_conn


def _wait_for_inbound_notify(listen_conn, timeout_seconds: float) -> List[int]:
    """
    Blocks up to timeout_seconds for Postgres NOTIFY and returns message ids.
    Payload format: {"message_id": <int>, ...}
    """
    if not listen_conn:
        return []

    message_ids: List[int] = []
    try:
        ready, _, _ = pyselect.select([listen_conn], [], [], timeout_seconds)
        if not ready:
            return []

        listen_conn.poll()
        notifications = list(getattr(listen_conn, "notifies", []) or [])
        if hasattr(listen_conn, "notifies"):
            listen_conn.notifies.clear()

        for notify in notifications:
            payload = getattr(notify, "payload", "") or ""
            if not payload:
                continue
            try:
                data = json.loads(payload)
                message_id = int(data.get("message_id"))
            except Exception:
                logger.warning("Inbound NOTIFY payload parse failed: %s", payload)
                continue
            if message_id > 0:
                _mark_worker_state(
                    last_notify_received_at=_iso_now(),
                    last_notified_message_id=message_id,
                    notify_events_total=INBOUND_WORKER_STATE.get("notify_events_total", 0) + 1,
                )
                message_ids.append(message_id)
    except Exception as exc:
        logger.warning("Inbound NOTIFY wait failed: %s", exc)
    return message_ids


def _claim_inbound_message(session: Session, message_id: int) -> Optional[UnifiedMessage]:
    """
    Atomically claim one inbound row for processing by transitioning:
    received -> inbound_processing.
    Returns the claimed UnifiedMessage or None if already claimed/invalid.
    """
    if engine.dialect.name == "postgresql":
        row = session.connection().execute(
            text(
                """
                UPDATE et_messages
                SET delivery_status = 'inbound_processing',
                    updated_at = NOW()
                WHERE id = :message_id
                  AND direction = 'inbound'
                  AND delivery_status = 'received'
                  AND thread_id IS NOT NULL
                RETURNING id
                """
            ),
            {"message_id": message_id},
        ).first()
        if not row:
            session.rollback()
            return None
        session.commit()
        if isinstance(row, (tuple, list)):
            claimed_raw = row[0]
        elif hasattr(row, "_mapping"):
            claimed_raw = next(iter(row._mapping.values()))
        else:
            claimed_raw = row
        claimed_id = int(claimed_raw)
        _mark_worker_state(
            last_claimed_at=_iso_now(),
            last_claimed_message_id=claimed_id,
            claimed_total=INBOUND_WORKER_STATE.get("claimed_total", 0) + 1,
        )
        return session.get(UnifiedMessage, claimed_id)

    # Non-Postgres fallback for local/test environments.
    message = session.get(UnifiedMessage, message_id)
    if (
        not message
        or message.direction != "inbound"
        or message.delivery_status != "received"
        or message.thread_id is None
    ):
        return None
    message.delivery_status = "inbound_processing"
    message.updated_at = datetime.utcnow()
    session.add(message)
    session.commit()
    session.refresh(message)
    _mark_worker_state(
        last_claimed_at=_iso_now(),
        last_claimed_message_id=message.id,
        claimed_total=INBOUND_WORKER_STATE.get("claimed_total", 0) + 1,
    )
    return message


def _mark_inbound_error(session: Session, message_id: int):
    db_inbound = session.get(UnifiedMessage, message_id)
    if db_inbound:
        db_inbound.delivery_status = "inbound_error"
        db_inbound.updated_at = datetime.utcnow()
        session.add(db_inbound)
        session.commit()
    _mark_worker_state(
        last_error_at=_iso_now(),
        last_error_message=f"inbound_error state set for message_id={message_id}",
        errors_total=INBOUND_WORKER_STATE.get("errors_total", 0) + 1,
    )


# ---------------------------------------------------------------------------
# Background worker loop
# ---------------------------------------------------------------------------

async def background_inbound_worker_loop():
    logger.info(
        "Starting inbound worker loop (poll=%ss, batch=%s)",
        INBOUND_POLL_SECONDS,
        INBOUND_BATCH_SIZE,
    )
    _mark_worker_state(started_at=_iso_now())
    listen_conn = None
    if engine.dialect.name == "postgresql":
        try:
            listen_conn = _open_inbound_listen_connection()
        except Exception as exc:
            logger.warning("Inbound LISTEN disabled (connect failed): %s", exc)
            listen_conn = None

    while True:
        _mark_worker_state(last_loop_at=_iso_now())
        processed = 0
        try:
            with Session(engine) as session:
                notified_ids: List[int] = []
                if listen_conn is not None:
                    notified_ids = await asyncio.to_thread(
                        _wait_for_inbound_notify,
                        listen_conn,
                        INBOUND_POLL_SECONDS,
                    )

                for message_id in list(dict.fromkeys(notified_ids)):
                    if processed >= INBOUND_BATCH_SIZE:
                        break
                    claimed = _claim_inbound_message(session, message_id)
                    if not claimed:
                        continue
                    try:
                        await _process_one_inbound(session, claimed)
                        processed += 1
                        _mark_worker_state(
                            last_processed_at=_iso_now(),
                            last_processed_message_id=message_id,
                            processed_total=INBOUND_WORKER_STATE.get("processed_total", 0) + 1,
                        )
                    except Exception as exc:
                        logger.exception(
                            "Inbound processing error for message_id=%s: %s",
                            message_id, exc,
                        )
                        _mark_worker_state(
                            last_error_at=_iso_now(),
                            last_error_message=f"message_id={message_id}: {exc}",
                            errors_total=INBOUND_WORKER_STATE.get("errors_total", 0) + 1,
                        )
                        session.rollback()
                        _mark_inbound_error(session, message_id)

                remaining = max(INBOUND_BATCH_SIZE - processed, 0)
                if remaining > 0:
                    inbound_batch = session.exec(
                        select(UnifiedMessage)
                        .where(
                            UnifiedMessage.direction == "inbound",
                            UnifiedMessage.delivery_status == "received",
                            UnifiedMessage.thread_id != None,
                        )
                        .order_by(UnifiedMessage.created_at.asc(), UnifiedMessage.id.asc())
                        .limit(remaining)
                    ).all()

                    for inbound in inbound_batch:
                        claimed = _claim_inbound_message(session, inbound.id)
                        if not claimed:
                            continue
                        try:
                            await _process_one_inbound(session, claimed)
                            processed += 1
                            _mark_worker_state(
                                last_processed_at=_iso_now(),
                                last_processed_message_id=inbound.id,
                                processed_total=INBOUND_WORKER_STATE.get("processed_total", 0) + 1,
                            )
                        except Exception as exc:
                            logger.exception(
                                "Inbound processing error for message_id=%s: %s",
                                inbound.id, exc,
                            )
                            _mark_worker_state(
                                last_error_at=_iso_now(),
                                last_error_message=f"message_id={inbound.id}: {exc}",
                                errors_total=INBOUND_WORKER_STATE.get("errors_total", 0) + 1,
                            )
                            session.rollback()
                            _mark_inbound_error(session, inbound.id)

        except Exception as exc:
            logger.exception("Inbound worker loop error: %s", exc)
            _mark_worker_state(
                last_error_at=_iso_now(),
                last_error_message=f"loop_error: {exc}",
                errors_total=INBOUND_WORKER_STATE.get("errors_total", 0) + 1,
            )
            if listen_conn is not None:
                try:
                    listen_conn.close()
                except Exception:
                    pass
                listen_conn = None
            if engine.dialect.name == "postgresql":
                try:
                    listen_conn = _open_inbound_listen_connection()
                except Exception as reconnect_exc:
                    logger.warning("Inbound LISTEN reconnect failed: %s", reconnect_exc)

        # If LISTEN is enabled, timeout wait already happened in _wait_for_inbound_notify.
        if processed == 0 and listen_conn is None:
            await asyncio.sleep(INBOUND_POLL_SECONDS)
        else:
            await asyncio.sleep(0)
