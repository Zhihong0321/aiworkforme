"""
MODULE: Messaging Core Routes
PURPOSE: Inbound/outbound/thread endpoints for unified messaging.
DOES: Queue outbound messages, create inbound events, and expose thread history.
DOES NOT: Manage WhatsApp session setup or MVP diagnostics.
INVARIANTS: Queueing/dispatch behavior and endpoint contracts stay stable.
SAFE CHANGE: Keep persistence side effects equivalent.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from src.adapters.api.dependencies import AuthContext, get_llm_router, require_tenant_access
from src.adapters.db.agent_models import Agent
from src.adapters.db.channel_models import ChannelSession, SessionStatus
from src.adapters.db.crm_models import Lead
from src.adapters.db.messaging_models import OutboundQueue, UnifiedMessage, UnifiedThread
from src.adapters.db.system_settings import get_bool_system_setting
from src.infra.database import get_session
from src.infra.llm.router import LLMRouter

from .messaging_helpers import (
    extract_whatsapp_recipient as _extract_whatsapp_recipient,
    get_or_create_thread as _get_or_create_thread,
    resolve_whatsapp_channel_session_for_tenant as _resolve_whatsapp_channel_session_for_tenant,
    stage_value as _stage_value,
    validate_channel_session as _validate_channel_session,
    validate_lead_number_for_whatsapp as _validate_lead_number_for_whatsapp,
    validate_lead_tenant as _validate_lead_tenant,
)
from .messaging_runtime import (
    dispatch_next_outbound_for_tenant,
    generate_initial_outreach_text as _generate_initial_outreach_text,
)
from .messaging_schemas import (
    DispatchResponse,
    InboundCreateRequest,
    LeadThreadDetailResponse,
    LeadWorkStartRequest,
    LeadWorkStartResponse,
    MessageCreateResponse,
    OutboundCreateRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/outbound", response_model=MessageCreateResponse)
def create_outbound_message(
    payload: OutboundCreateRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    channel = payload.channel.strip().lower()
    if channel not in {"whatsapp", "email", "telegram"}:
        raise HTTPException(status_code=400, detail="Unsupported channel")
    if not payload.text_content.strip():
        raise HTTPException(status_code=400, detail="text_content is required")
    if channel == "whatsapp" and payload.channel_session_id is None:
        raise HTTPException(status_code=400, detail="channel_session_id is required for WhatsApp outbound")

    lead = _validate_lead_tenant(session, payload.lead_id, auth.tenant.id)
    _validate_channel_session(session, auth.tenant.id, channel, payload.channel_session_id)

    thread = _get_or_create_thread(session, auth.tenant.id, lead.id, channel)
    external_message_id = payload.external_message_id or f"out_{uuid4().hex}"
    now = datetime.utcnow()

    message = UnifiedMessage(
        tenant_id=auth.tenant.id,
        lead_id=lead.id,
        thread_id=thread.id,
        channel_session_id=payload.channel_session_id,
        channel=channel,
        external_message_id=external_message_id,
        direction="outbound",
        message_type="text",
        text_content=payload.text_content,
        raw_payload=payload.raw_payload or {},
        delivery_status="queued",
        created_at=now,
        updated_at=now,
    )
    session.add(message)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Duplicate outbound message id") from exc
    session.refresh(message)

    queue = OutboundQueue(
        tenant_id=auth.tenant.id,
        message_id=message.id,
        channel=channel,
        channel_session_id=payload.channel_session_id,
        status="queued",
        retry_count=0,
        next_attempt_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(queue)
    session.commit()
    session.refresh(queue)

    return MessageCreateResponse(
        message_id=message.id,
        thread_id=message.thread_id,
        queue_id=queue.id,
        status=queue.status,
    )


@router.post("/leads/{lead_id}/start-work", response_model=LeadWorkStartResponse)
async def start_lead_work(
    lead_id: int,
    payload: LeadWorkStartRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
    router: LLMRouter = Depends(get_llm_router),
):
    channel = (payload.channel or "").strip().lower()
    if channel != "whatsapp":
        raise HTTPException(status_code=400, detail="Only whatsapp is supported right now")

    lead = _validate_lead_tenant(session, lead_id, auth.tenant.id)
    _validate_lead_number_for_whatsapp(lead)
    channel_session = _resolve_whatsapp_channel_session_for_tenant(
        session=session,
        tenant_id=auth.tenant.id,
        channel_session_id=payload.channel_session_id,
    )
    if channel_session.status != SessionStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail="WhatsApp session is not active. Refresh/scan QR in Channel Setup first.",
        )

    thread = _get_or_create_thread(session, auth.tenant.id, lead.id, channel)
    if not thread.agent_id:
        raise HTTPException(status_code=400, detail="No agent assigned for this thread")
    agent = session.get(Agent, thread.agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=400, detail="Assigned agent is unavailable")

    include_context_prompt = get_bool_system_setting(
        session, "record_context_prompt", default=False
    )
    text_content, ai_trace = await _generate_initial_outreach_text(
        router, agent, lead, include_context_prompt
    )
    usage = ai_trace.get("usage") if isinstance(ai_trace.get("usage"), dict) else {}
    now = datetime.utcnow()
    message = UnifiedMessage(
        tenant_id=auth.tenant.id,
        lead_id=lead.id,
        thread_id=thread.id,
        channel_session_id=channel_session.id,
        channel=channel,
        external_message_id=f"out_{uuid4().hex}",
        direction="outbound",
        message_type="text",
        text_content=text_content,
        llm_provider=ai_trace.get("provider"),
        llm_model=ai_trace.get("model"),
        llm_prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
        llm_completion_tokens=int(usage.get("completion_tokens", 0) or 0),
        llm_total_tokens=int(usage.get("total_tokens", 0) or 0),
        llm_estimated_cost_usd=float(usage.get("estimated_cost_usd", 0) or 0),
        raw_payload={"source": "manual_working_mode", "agent_id": agent.id, "ai_trace": ai_trace},
        delivery_status="queued",
        created_at=now,
        updated_at=now,
    )
    session.add(message)
    session.commit()
    session.refresh(message)

    queue = OutboundQueue(
        tenant_id=auth.tenant.id,
        message_id=message.id,
        channel=channel,
        channel_session_id=channel_session.id,
        status="queued",
        retry_count=0,
        next_attempt_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(queue)
    session.commit()
    session.refresh(queue)

    dispatch_status = queue.status
    dispatch_detail: Optional[str] = None
    try:
        # Try immediate dispatch so "Working" feels instant instead of waiting for poll loop.
        for _ in range(5):
            dispatched = dispatch_next_outbound_for_tenant(session, auth.tenant.id)
            if not dispatched:
                break
            if dispatched.message_id == message.id:
                dispatch_status = dispatched.status
                dispatch_detail = dispatched.detail
                break
    except Exception as exc:
        logger.warning(
            "Immediate dispatch attempt failed for lead_id=%s message_id=%s: %s",
            lead.id,
            message.id,
            exc,
        )

    mode_tags = [str(t) for t in (lead.tags or []) if str(t) not in {"ON_HOLD", "WORKING"}]
    mode_tags.append("WORKING")
    lead.tags = mode_tags
    if _stage_value(lead.stage) == "NEW":
        lead.stage = "CONTACTED"
    lead.last_followup_review_at = datetime.utcnow()
    session.add(lead)
    session.commit()
    session.refresh(message)

    provider_message_id = None
    if isinstance(message.raw_payload, dict):
        provider_message_id = message.raw_payload.get("provider_message_id")
    recipient = _extract_whatsapp_recipient(lead.external_id)
    if dispatch_status in {"sent", "accepted"} and provider_message_id:
        if dispatch_status == "accepted":
            dispatch_detail = f"Accepted by provider for {recipient} (delivery pending, provider id: {provider_message_id})"
        else:
            dispatch_detail = f"Sent to {recipient} (provider id: {provider_message_id})"

    return LeadWorkStartResponse(
        lead_id=lead.id,
        message_id=message.id,
        queue_id=queue.id,
        thread_id=thread.id or 0,
        channel_session_id=channel_session.id,
        status=dispatch_status,
        detail=dispatch_detail,
        recipient=recipient,
        provider_message_id=str(provider_message_id) if provider_message_id else None,
    )
@router.post("/inbound", response_model=MessageCreateResponse)
def create_inbound_message(
    payload: InboundCreateRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    channel = payload.channel.strip().lower()
    if channel not in {"whatsapp", "email", "telegram"}:
        raise HTTPException(status_code=400, detail="Unsupported channel")

    lead = _validate_lead_tenant(session, payload.lead_id, auth.tenant.id)
    _validate_channel_session(session, auth.tenant.id, channel, payload.channel_session_id)

    now = datetime.utcnow()
    message = UnifiedMessage(
        tenant_id=auth.tenant.id,
        lead_id=lead.id,
        thread_id=None,  # expected to be assigned by DB trigger on PostgreSQL
        channel_session_id=payload.channel_session_id,
        channel=channel,
        external_message_id=payload.external_message_id,
        direction="inbound",
        message_type=payload.message_type,
        text_content=payload.text_content,
        media_url=payload.media_url,
        raw_payload=payload.raw_payload or {},
        delivery_status="received",
        created_at=now,
        updated_at=now,
    )
    session.add(message)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Duplicate inbound message") from exc
    session.refresh(message)

    # Fallback for non-PostgreSQL environments where trigger is not installed.
    if message.thread_id is None:
        thread = _get_or_create_thread(session, auth.tenant.id, lead.id, channel)
        message.thread_id = thread.id
        message.updated_at = datetime.utcnow()
        session.add(message)
        session.commit()
        session.refresh(message)

    return MessageCreateResponse(
        message_id=message.id,
        thread_id=message.thread_id,
        status=message.delivery_status,
    )


@router.get("/threads/{thread_id}/messages", response_model=List[UnifiedMessage])
def list_thread_messages(
    thread_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    thread = session.get(UnifiedThread, thread_id)
    if not thread or thread.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Thread not found")

    return session.exec(
        select(UnifiedMessage)
        .where(
            UnifiedMessage.tenant_id == auth.tenant.id,
            UnifiedMessage.thread_id == thread_id,
        )
        .order_by(UnifiedMessage.created_at.asc())
    ).all()


@router.get("/leads/{lead_id}/thread", response_model=LeadThreadDetailResponse)
def get_lead_thread_detail(
    lead_id: int,
    channel: str = "whatsapp",
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    lead = _validate_lead_tenant(session, lead_id, auth.tenant.id)
    normalized_channel = (channel or "").strip().lower()
    thread = session.exec(
        select(UnifiedThread)
        .where(
            UnifiedThread.tenant_id == auth.tenant.id,
            UnifiedThread.lead_id == lead.id,
            UnifiedThread.channel == normalized_channel,
        )
        .order_by(UnifiedThread.id.desc())
    ).first()
    if not thread:
        raise HTTPException(status_code=404, detail="No thread found for this lead yet")

    messages = session.exec(
        select(UnifiedMessage)
        .where(
            UnifiedMessage.tenant_id == auth.tenant.id,
            UnifiedMessage.thread_id == thread.id,
        )
        .order_by(UnifiedMessage.created_at.asc())
    ).all()

    return LeadThreadDetailResponse(
        thread_id=thread.id,
        lead_id=lead.id,
        channel=thread.channel,
        status=thread.status,
        messages=messages,
    )


@router.post("/outbound/dispatch-next", response_model=DispatchResponse)
def dispatch_next_outbound(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    result = dispatch_next_outbound_for_tenant(session, auth.tenant.id)
    if not result:
        raise HTTPException(status_code=404, detail="No queued outbound message")
    return result
