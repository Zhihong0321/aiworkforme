"""
MODULE: Messaging MVP Diagnostic Routes
PURPOSE: MVP operational health/debug/simulation endpoints.
DOES: Expose readiness checks and inbound simulation helpers.
DOES NOT: Manage channel provisioning or generic outbound creation.
INVARIANTS: Diagnostic endpoint response shapes remain stable.
SAFE CHANGE: Preserve non-blocking diagnostic semantics.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from src.adapters.api.dependencies import AuthContext, llm_router, require_tenant_access
from src.adapters.db.agent_models import Agent
from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.messaging_models import OutboundQueue, UnifiedMessage
from src.infra.database import get_session

from .messaging_helpers import (
    get_or_create_thread as _get_or_create_thread,
    resolve_whatsapp_channel_session_for_tenant as _resolve_whatsapp_channel_session_for_tenant,
    validate_lead_number_for_whatsapp as _validate_lead_number_for_whatsapp,
    validate_lead_tenant as _validate_lead_tenant,
)
from .messaging_runtime import dispatch_next_outbound_for_tenant
from .messaging_schemas import (
    InboundDebugResponse,
    InboundHealthResponse,
    MVPOperationalCheckResponse,
    SimulateInboundRequest,
    SimulateInboundResponse,
)

router = APIRouter()

@router.get("/mvp/operational-check", response_model=MVPOperationalCheckResponse)
def mvp_operational_check(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    tenant_id = auth.tenant.id
    checks: Dict[str, Any] = {}
    blockers: List[str] = []

    workspaces = session.exec(
        select(Workspace).where(Workspace.tenant_id == tenant_id)
    ).all()
    checks["workspace_count"] = len(workspaces)
    if not workspaces:
        blockers.append("No workspace found for tenant.")

    agents = session.exec(
        select(Agent).where(Agent.tenant_id == tenant_id)
    ).all()
    checks["agent_count"] = len(agents)
    if not agents:
        blockers.append("No AI agent found for tenant.")

    workspace_with_agent = any(w.agent_id for w in workspaces)
    checks["workspace_has_agent"] = workspace_with_agent
    if not workspace_with_agent:
        blockers.append("No workspace is linked to an AI agent.")

    leads = session.exec(
        select(Lead).where(Lead.tenant_id == tenant_id)
    ).all()
    checks["lead_count"] = len(leads)
    valid_lead_count = 0
    for lead in leads:
        try:
            _validate_lead_number_for_whatsapp(lead)
            valid_lead_count += 1
        except Exception:
            pass
    checks["valid_whatsapp_lead_count"] = valid_lead_count
    if valid_lead_count == 0:
        blockers.append("No lead with valid WhatsApp number found (8-15 digits with country code).")

    sessions = session.exec(
        select(ChannelSession).where(
            ChannelSession.tenant_id == tenant_id,
            ChannelSession.channel_type == ChannelType.WHATSAPP,
        )
    ).all()
    checks["whatsapp_session_count"] = len(sessions)
    active_sessions = [
        s for s in sessions
        if s.status == SessionStatus.ACTIVE
    ]
    checks["whatsapp_active_session_count"] = len(active_sessions)
    checks["whatsapp_active_session_ids"] = [s.id for s in active_sessions]
    if not active_sessions:
        blockers.append("No active WhatsApp channel session. Reconnect QR in Channel Setup.")

    queue_backlog = session.exec(
        select(OutboundQueue).where(
            OutboundQueue.tenant_id == tenant_id,
            OutboundQueue.status == "queued",
        )
    ).all()
    checks["queued_outbound_count"] = len(queue_backlog)

    inbound_received = session.exec(
        select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == tenant_id,
            UnifiedMessage.direction == "inbound",
            UnifiedMessage.delivery_status == "received",
        )
    ).all()
    checks["inbound_received_unprocessed"] = len(inbound_received)

    # LLM provider health snapshot (non-blocking for MVP because inbound has fallback reply).
    llm_health: Dict[str, bool] = {}
    for provider_name, provider in llm_router.providers.items():
        try:
            llm_health[provider_name] = bool(provider.is_healthy())
        except Exception:
            llm_health[provider_name] = False
    checks["llm_provider_health"] = llm_health

    return MVPOperationalCheckResponse(
        ready=len(blockers) == 0,
        checks=checks,
        blockers=blockers,
    )


@router.get("/mvp/inbound-health", response_model=InboundHealthResponse)
def mvp_inbound_health(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    tenant_id = auth.tenant.id
    checks: Dict[str, Any] = {}
    blockers: List[str] = []

    from src.app.background_tasks_inbound import INBOUND_NOTIFY_CHANNEL, INBOUND_POLL_SECONDS

    checks["db_engine"] = session.bind.dialect.name if session.bind else "unknown"
    checks["notify_channel"] = INBOUND_NOTIFY_CHANNEL
    checks["poll_seconds"] = INBOUND_POLL_SECONDS
    checks["supports_listen_notify"] = checks["db_engine"] == "postgresql"
    if not checks["supports_listen_notify"]:
        blockers.append("Database is not PostgreSQL; LISTEN/NOTIFY is disabled.")

    now = datetime.utcnow()
    stale_cutoff = now - timedelta(minutes=5)

    received_unprocessed = session.exec(
        select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == tenant_id,
            UnifiedMessage.direction == "inbound",
            UnifiedMessage.delivery_status == "received",
        )
    ).all()
    checks["inbound_received_unprocessed"] = len(received_unprocessed)

    checks["inbound_received_stuck_over_5m"] = len(
        [m for m in received_unprocessed if m.created_at and m.created_at < stale_cutoff]
    )
    if checks["inbound_received_stuck_over_5m"] > 0:
        blockers.append("There are inbound messages stuck in 'received' for over 5 minutes.")

    last_processed = session.exec(
        select(UnifiedMessage)
        .where(
            UnifiedMessage.tenant_id == tenant_id,
            UnifiedMessage.direction == "inbound",
            UnifiedMessage.delivery_status.in_(
                ["inbound_ai_replied", "inbound_human_takeover", "inbound_error"]
            ),
        )
        .order_by(UnifiedMessage.updated_at.desc(), UnifiedMessage.id.desc())
    ).first()
    checks["last_processed_inbound_message_id"] = last_processed.id if last_processed else None
    checks["last_processed_inbound_at"] = (
        last_processed.updated_at.isoformat() if last_processed and last_processed.updated_at else None
    )

    worker_mode = (
        "listen_notify_with_poll_fallback"
        if checks["supports_listen_notify"]
        else "poll_only"
    )

    return InboundHealthResponse(
        ready=len(blockers) == 0,
        worker_mode=worker_mode,
        notify_channel=INBOUND_NOTIFY_CHANNEL,
        checks=checks,
        blockers=blockers,
    )


@router.get("/mvp/inbound-debug", response_model=InboundDebugResponse)
def mvp_inbound_debug(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    tenant_id = auth.tenant.id

    from src.app.background_tasks_inbound import get_inbound_worker_debug_snapshot

    recent_inbound_rows = session.exec(
        select(UnifiedMessage)
        .where(
            UnifiedMessage.tenant_id == tenant_id,
            UnifiedMessage.direction == "inbound",
        )
        .order_by(UnifiedMessage.id.desc())
        .limit(20)
    ).all()
    recent_inbound = [
        {
            "id": row.id,
            "thread_id": row.thread_id,
            "lead_id": row.lead_id,
            "channel": row.channel,
            "delivery_status": row.delivery_status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "text_preview": (row.text_content or "")[:120],
        }
        for row in recent_inbound_rows
    ]

    outbound_rows = session.exec(
        select(UnifiedMessage)
        .where(
            UnifiedMessage.tenant_id == tenant_id,
            UnifiedMessage.direction == "outbound",
        )
        .order_by(UnifiedMessage.id.desc())
        .limit(50)
    ).all()
    recent_outbound_from_inbound = [
        {
            "id": row.id,
            "thread_id": row.thread_id,
            "lead_id": row.lead_id,
            "delivery_status": row.delivery_status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "source": row.raw_payload.get("source") if isinstance(row.raw_payload, dict) else None,
            "inbound_message_id": (
                row.raw_payload.get("inbound_message_id")
                if isinstance(row.raw_payload, dict)
                else None
            ),
            "text_preview": (row.text_content or "")[:120],
        }
        for row in outbound_rows
        if isinstance(row.raw_payload, dict) and row.raw_payload.get("inbound_message_id") is not None
    ][:20]

    queue_rows = session.exec(
        select(OutboundQueue)
        .where(OutboundQueue.tenant_id == tenant_id)
        .order_by(OutboundQueue.id.desc())
        .limit(20)
    ).all()
    queue_snapshot = [
        {
            "id": q.id,
            "message_id": q.message_id,
            "channel": q.channel,
            "status": q.status,
            "retry_count": q.retry_count,
            "next_attempt_at": q.next_attempt_at.isoformat() if q.next_attempt_at else None,
            "last_error": q.last_error,
            "updated_at": q.updated_at.isoformat() if q.updated_at else None,
        }
        for q in queue_rows
    ]

    return InboundDebugResponse(
        worker_state=get_inbound_worker_debug_snapshot(),
        recent_inbound=recent_inbound,
        recent_outbound_from_inbound=recent_outbound_from_inbound,
        queue_snapshot=queue_snapshot,
    )


@router.post("/mvp/simulate-inbound", response_model=SimulateInboundResponse)
async def simulate_inbound_message(
    payload: SimulateInboundRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    channel = (payload.channel or "").strip().lower()
    if channel != "whatsapp":
        raise HTTPException(status_code=400, detail="simulate-inbound currently supports whatsapp only")
    if not (payload.text_content or "").strip():
        raise HTTPException(status_code=400, detail="text_content is required")

    lead = _validate_lead_tenant(session, payload.lead_id, auth.tenant.id)
    channel_session = _resolve_whatsapp_channel_session_for_tenant(
        session=session,
        tenant_id=auth.tenant.id,
        channel_session_id=payload.channel_session_id,
    )

    thread = _get_or_create_thread(session, auth.tenant.id, lead.id, channel)
    now = datetime.utcnow()
    inbound = UnifiedMessage(
        tenant_id=auth.tenant.id,
        lead_id=lead.id,
        thread_id=thread.id,
        channel_session_id=channel_session.id,
        channel=channel,
        external_message_id=f"in_{uuid4().hex}",
        direction="inbound",
        message_type="text",
        text_content=payload.text_content.strip(),
        raw_payload={"source": "mvp_simulate_inbound"},
        delivery_status="received",
        created_at=now,
        updated_at=now,
    )
    session.add(inbound)
    session.commit()
    session.refresh(inbound)

    from src.app.background_tasks_inbound import _process_one_inbound  # local import to avoid startup cycles
    try:
        await _process_one_inbound(session, inbound)
    except Exception as exc:
        inbound.delivery_status = "inbound_error"
        inbound.updated_at = datetime.utcnow()
        session.add(inbound)
        session.commit()
        return SimulateInboundResponse(
            inbound_message_id=inbound.id,
            thread_id=thread.id or 0,
            inbound_status=inbound.delivery_status,
            detail=f"Inbound simulation failed: {str(exc)}",
        )
    session.refresh(inbound)

    outbound_candidates = session.exec(
        select(UnifiedMessage)
        .where(
            UnifiedMessage.tenant_id == auth.tenant.id,
            UnifiedMessage.thread_id == thread.id,
            UnifiedMessage.direction == "outbound",
        )
        .order_by(UnifiedMessage.id.desc())
    ).all()
    queued_reply = next(
        (
            row for row in outbound_candidates
            if isinstance(row.raw_payload, dict) and row.raw_payload.get("source") == "inbound_worker"
        ),
        None,
    )

    queued_reply_queue_id = None
    if queued_reply:
        queue_row = session.exec(
            select(OutboundQueue).where(OutboundQueue.message_id == queued_reply.id)
        ).first()
        queued_reply_queue_id = queue_row.id if queue_row else None

    dispatch_result = dispatch_next_outbound_for_tenant(session, auth.tenant.id)
    detail = None
    if dispatch_result and queued_reply and dispatch_result.message_id == queued_reply.id:
        detail = f"Inbound processed; auto-reply dispatch status: {dispatch_result.status}"
    elif inbound.delivery_status == "inbound_human_takeover":
        detail = "Inbound processed; AI chose human_takeover (no auto reply queued)."
    else:
        detail = "Inbound processed."

    return SimulateInboundResponse(
        inbound_message_id=inbound.id,
        thread_id=thread.id or 0,
        inbound_status=inbound.delivery_status,
        queued_reply_message_id=queued_reply.id if queued_reply else None,
        queued_reply_queue_id=queued_reply_queue_id,
        detail=detail,
    )
