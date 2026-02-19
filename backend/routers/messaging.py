import os
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import quote
from uuid import uuid4
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from src.infra.database import get_session
from src.adapters.api.dependencies import require_tenant_access, AuthContext, get_llm_router, llm_router
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.agent_models import Agent
from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.messaging_models import UnifiedThread, UnifiedMessage, OutboundQueue
from src.adapters.db.system_settings import get_bool_system_setting
from src.infra.llm.router import LLMRouter
from src.infra.llm.schemas import LLMTask
from src.infra.llm.costs import estimate_llm_cost_usd


router = APIRouter(prefix="/api/v1/messaging", tags=["Unified Messaging"])
logger = logging.getLogger(__name__)


class OutboundCreateRequest(SQLModel):
    lead_id: int
    channel: str
    text_content: str
    channel_session_id: Optional[int] = None
    external_message_id: Optional[str] = None
    raw_payload: Dict[str, Any] = {}


class InboundCreateRequest(SQLModel):
    lead_id: int
    channel: str
    external_message_id: str
    text_content: Optional[str] = None
    message_type: str = "text"
    channel_session_id: Optional[int] = None
    raw_payload: Dict[str, Any] = {}


class MessageCreateResponse(SQLModel):
    message_id: int
    thread_id: Optional[int]
    queue_id: Optional[int] = None
    status: str


class DispatchResponse(SQLModel):
    queue_id: int
    message_id: int
    channel: str
    status: str
    retry_count: int
    detail: Optional[str] = None


class LeadWorkStartRequest(SQLModel):
    channel: str = "whatsapp"
    channel_session_id: Optional[int] = None


class LeadWorkStartResponse(SQLModel):
    lead_id: int
    message_id: int
    queue_id: int
    thread_id: int
    channel_session_id: int
    status: str
    detail: Optional[str] = None
    recipient: Optional[str] = None
    provider_message_id: Optional[str] = None


class WhatsAppConnectRequest(SQLModel):
    session_key: str = "primary"
    display_name: Optional[str] = None
    provider_base_url: Optional[str] = None


class WhatsAppRefreshResponse(SQLModel):
    channel_session_id: int
    session_identifier: str
    status: str
    remote: Dict[str, Any] = {}


class LeadThreadDetailResponse(SQLModel):
    thread_id: int
    lead_id: int
    channel: str
    status: str
    messages: List[UnifiedMessage]


class MVPOperationalCheckResponse(SQLModel):
    ready: bool
    checks: Dict[str, Any]
    blockers: List[str]


class InboundHealthResponse(SQLModel):
    ready: bool
    worker_mode: str
    notify_channel: str
    checks: Dict[str, Any]
    blockers: List[str]


class InboundDebugResponse(SQLModel):
    worker_state: Dict[str, Any]
    recent_inbound: List[Dict[str, Any]]
    recent_outbound_from_inbound: List[Dict[str, Any]]
    queue_snapshot: List[Dict[str, Any]]


class SimulateInboundRequest(SQLModel):
    lead_id: int
    text_content: str
    channel: str = "whatsapp"
    channel_session_id: Optional[int] = None


class SimulateInboundResponse(SQLModel):
    inbound_message_id: int
    thread_id: int
    inbound_status: str
    queued_reply_message_id: Optional[int] = None
    queued_reply_queue_id: Optional[int] = None
    detail: Optional[str] = None


def _validate_lead_tenant(session: Session, lead_id: int, tenant_id: int) -> Lead:
    lead = session.get(Lead, lead_id)
    if not lead or lead.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


def _stage_value(stage) -> str:
    return stage.value if hasattr(stage, "value") else str(stage)


def _validate_channel_session(
    session: Session,
    tenant_id: int,
    channel: str,
    channel_session_id: Optional[int],
) -> Optional[ChannelSession]:
    if channel_session_id is None:
        return None

    channel_session = session.get(ChannelSession, channel_session_id)
    if not channel_session or channel_session.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Channel session not found")

    if str(channel_session.channel_type.value if hasattr(channel_session.channel_type, "value") else channel_session.channel_type) != channel:
        raise HTTPException(status_code=400, detail="Channel session does not match channel")

    return channel_session


def _get_or_create_thread(session: Session, tenant_id: int, lead_id: int, channel: str) -> UnifiedThread:
    thread = session.exec(
        select(UnifiedThread).where(
            UnifiedThread.tenant_id == tenant_id,
            UnifiedThread.lead_id == lead_id,
            UnifiedThread.channel == channel,
            UnifiedThread.status == "active",
        )
    ).first()

    if thread:
        if thread.agent_id is None:
            thread.agent_id = _resolve_agent_for_lead(session, tenant_id, lead_id)
            thread.updated_at = datetime.utcnow()
            session.add(thread)
            session.commit()
            session.refresh(thread)
        return thread

    agent_id = _resolve_agent_for_lead(session, tenant_id, lead_id)
    thread = UnifiedThread(
        tenant_id=tenant_id,
        lead_id=lead_id,
        agent_id=agent_id,
        channel=channel,
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(thread)
    session.commit()
    session.refresh(thread)
    return thread


def _resolve_agent_for_lead(session: Session, tenant_id: int, lead_id: int) -> int:
    lead = session.get(Lead, lead_id)
    if not lead or lead.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    workspace = session.get(Workspace, lead.workspace_id)
    if workspace and workspace.tenant_id == tenant_id and workspace.agent_id is not None:
        agent = session.get(Agent, workspace.agent_id)
        if agent and agent.tenant_id == tenant_id:
            return agent.id

    fallback_agent = session.exec(
        select(Agent)
        .where(Agent.tenant_id == tenant_id)
        .order_by(Agent.id.asc())
    ).first()
    if fallback_agent:
        return fallback_agent.id

    raise HTTPException(
        status_code=400,
        detail="No AI agent is configured for tenant. Assign a workspace agent first.",
    )


def _provider_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    api_key = os.getenv("WHATSAPP_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _normalize_session_key(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", (value or "").strip()).strip("-").lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="session_key is required")
    if len(normalized) > 64:
        raise HTTPException(status_code=400, detail="session_key is too long (max 64)")
    return normalized


def _resolve_whatsapp_base_url(channel_session: Optional[ChannelSession] = None, override_url: Optional[str] = None) -> str:
    if override_url:
        return override_url.rstrip("/")
    if channel_session and isinstance(channel_session.session_metadata, dict):
        provider_base_url = channel_session.session_metadata.get("provider_base_url")
        if provider_base_url:
            return str(provider_base_url).rstrip("/")

    env_url = os.getenv("WHATSAPP_API_BASE_URL")
    if env_url:
        return env_url.rstrip("/")
    raise HTTPException(status_code=500, detail="WHATSAPP_API_BASE_URL is not configured")


def _extract_whatsapp_recipient(lead_external_id: Optional[str]) -> str:
    if not lead_external_id:
        raise RuntimeError("Lead external_id is required for WhatsApp send")

    raw = str(lead_external_id).strip()
    if "@s.whatsapp.net" in raw:
        return raw.split("@", 1)[0]

    digits = re.sub(r"\D+", "", raw)
    if not digits:
        raise RuntimeError("Lead external_id has no valid WhatsApp number")
    return digits


def _validate_lead_number_for_whatsapp(lead: Lead) -> str:
    recipient = _extract_whatsapp_recipient(lead.external_id)
    if not (8 <= len(recipient) <= 15):
        raise HTTPException(
            status_code=400,
            detail="Lead external_id must be a valid WhatsApp number (8-15 digits with country code).",
        )
    return recipient


def _upsert_whatsapp_channel_session(
    session: Session,
    tenant_id: int,
    session_identifier: str,
    display_name: Optional[str],
    provider_base_url: Optional[str],
) -> ChannelSession:
    channel_session = session.exec(
        select(ChannelSession).where(
            ChannelSession.tenant_id == tenant_id,
            ChannelSession.channel_type == ChannelType.WHATSAPP,
            ChannelSession.session_identifier == session_identifier,
        )
    ).first()

    now = datetime.utcnow()
    if not channel_session:
        channel_session = ChannelSession(
            tenant_id=tenant_id,
            channel_type=ChannelType.WHATSAPP,
            session_identifier=session_identifier,
            display_name=display_name or f"WhatsApp {session_identifier}",
            status=SessionStatus.DISCONNECTED,
            session_metadata={},
            created_at=now,
            updated_at=now,
        )
    else:
        if display_name:
            channel_session.display_name = display_name
        channel_session.updated_at = now

    metadata = dict(channel_session.session_metadata or {})
    if provider_base_url:
        metadata["provider_base_url"] = provider_base_url.rstrip("/")
    channel_session.session_metadata = metadata
    session.add(channel_session)
    session.commit()
    session.refresh(channel_session)
    return channel_session


def _assert_whatsapp_channel_session_for_tenant(
    session: Session,
    tenant_id: int,
    channel_session_id: int,
) -> ChannelSession:
    channel_session = session.get(ChannelSession, channel_session_id)
    if not channel_session or channel_session.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Channel session not found")
    channel_type = (
        channel_session.channel_type.value
        if hasattr(channel_session.channel_type, "value")
        else str(channel_session.channel_type)
    )
    if channel_type != "whatsapp":
        raise HTTPException(status_code=400, detail="Channel session is not WhatsApp")
    return channel_session


def _map_remote_status_to_local(remote_status: Optional[str]) -> SessionStatus:
    value = str(remote_status or "").strip().lower()
    if value in {"connected", "active", "live", "ready"}:
        return SessionStatus.ACTIVE
    return SessionStatus.DISCONNECTED


def _channel_send_url(channel: str) -> Optional[str]:
    mapping = {
        "email": os.getenv("EMAIL_CHANNEL_SEND_URL"),
        "telegram": os.getenv("TELEGRAM_CHANNEL_SEND_URL"),
    }
    return mapping.get(channel)


def _mark_retry(queue: OutboundQueue, message: UnifiedMessage, err: str):
    queue.retry_count += 1
    queue.updated_at = datetime.utcnow()
    queue.last_error = err
    if queue.retry_count >= 3:
        queue.status = "failed"
        message.delivery_status = "failed"
    else:
        queue.status = "queued"
        queue.next_attempt_at = datetime.utcnow() + timedelta(minutes=2 ** queue.retry_count)
        message.delivery_status = "retry_scheduled"
    message.updated_at = datetime.utcnow()


def _resolve_whatsapp_channel_session_for_tenant(
    session: Session,
    tenant_id: int,
    channel_session_id: Optional[int],
) -> ChannelSession:
    if channel_session_id is not None:
        channel_session = session.get(ChannelSession, channel_session_id)
        if not channel_session or channel_session.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Channel session not found")
        channel_type = (
            channel_session.channel_type.value
            if hasattr(channel_session.channel_type, "value")
            else str(channel_session.channel_type)
        )
        if channel_type != "whatsapp":
            raise HTTPException(status_code=400, detail="Channel session must be WhatsApp")
        return channel_session

    active = session.exec(
        select(ChannelSession)
        .where(
            ChannelSession.tenant_id == tenant_id,
            ChannelSession.channel_type == ChannelType.WHATSAPP,
            ChannelSession.status == SessionStatus.ACTIVE,
        )
        .order_by(ChannelSession.id.asc())
    ).first()
    if active:
        return active

    any_session = session.exec(
        select(ChannelSession)
        .where(
            ChannelSession.tenant_id == tenant_id,
            ChannelSession.channel_type == ChannelType.WHATSAPP,
        )
        .order_by(ChannelSession.id.asc())
    ).first()
    if not any_session:
        raise HTTPException(status_code=400, detail="No WhatsApp session found. Connect channel first.")
    return any_session


def _normalize_usage(usage: Dict[str, Any]) -> Dict[str, Any]:
    usage = usage or {}
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", 0) or 0)
    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "raw_usage": usage.get("raw_usage", usage),
    }


async def _generate_initial_outreach_text(
    router: LLMRouter, agent: Agent, lead: Lead, include_context_prompt: bool
) -> Tuple[str, Dict[str, Any]]:
    lead_name = lead.name or "there"
    prompt = (
        "Generate one short first outreach WhatsApp message for this lead. "
        "Keep it natural, polite, and action-oriented. No markdown."
        f"\nLead name: {lead_name}\nLead contact id: {lead.external_id}"
    )
    try:
        response = await router.execute(
            task=LLMTask.CONVERSATION,
            messages=[
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=220,
            model=getattr(agent, "model", None),
        )
        text = (response.content or "").strip()
        if text:
            provider_info = response.provider_info or {}
            ai_trace = {
                "schema_version": "1.0",
                "task": LLMTask.CONVERSATION.value,
                "provider": provider_info.get("provider") or "unknown",
                "model": provider_info.get("model") or "unknown",
                "usage": _normalize_usage(response.usage or {}),
                "context_prompt": agent.system_prompt if include_context_prompt else None,
                "recorded_at": datetime.utcnow().isoformat(),
            }
            usage = ai_trace["usage"]
            ai_trace["usage"]["estimated_cost_usd"] = estimate_llm_cost_usd(
                ai_trace["provider"],
                ai_trace["model"],
                usage.get("prompt_tokens", 0) or 0,
                usage.get("completion_tokens", 0) or 0,
            )
            return text, ai_trace
    except Exception as exc:
        logger.warning("Initial outreach generation failed for lead_id=%s: %s", lead.id, exc)
    return (
        f"Hi {lead_name}, I wanted to follow up and see how I can help you today.",
        {
            "schema_version": "1.0",
            "task": LLMTask.CONVERSATION.value,
            "provider": "fallback_template",
            "model": "none",
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "raw_usage": {},
                "estimated_cost_usd": 0,
            },
            "context_prompt": agent.system_prompt if include_context_prompt else None,
            "recorded_at": datetime.utcnow().isoformat(),
        },
    )


def _send_whatsapp_message(session: Session, message: UnifiedMessage) -> str:
    if not message.channel_session_id:
        raise RuntimeError("WhatsApp outbound requires channel_session_id")

    channel_session = session.get(ChannelSession, message.channel_session_id)
    if not channel_session or channel_session.tenant_id != message.tenant_id:
        raise RuntimeError("Invalid WhatsApp channel session")
    channel_type = (
        channel_session.channel_type.value
        if hasattr(channel_session.channel_type, "value")
        else str(channel_session.channel_type)
    )
    if channel_type != "whatsapp":
        raise RuntimeError("channel_session_id is not a WhatsApp session")
    if channel_session.status != SessionStatus.ACTIVE:
        raise RuntimeError("WhatsApp session is not active")

    lead = session.get(Lead, message.lead_id)
    if not lead or lead.tenant_id != message.tenant_id:
        raise RuntimeError("Lead not found for outbound message")

    base_url = _resolve_whatsapp_base_url(channel_session)
    endpoint = f"{base_url}/messages/send"
    payload = {
        "sessionId": channel_session.session_identifier,
        "to": _extract_whatsapp_recipient(lead.external_id),
        "text": message.text_content or "",
    }

    with httpx.Client(timeout=20.0) as client:
        resp = client.post(endpoint, headers=_provider_headers(), json=payload)
        resp.raise_for_status()
        body = resp.json() if resp.content else {}

    result = body.get("result") or {}
    key = result.get("key") if isinstance(result, dict) else {}
    provider_message_id = (
        body.get("provider_message_id")
        or body.get("message_id")
        or (key.get("id") if isinstance(key, dict) else None)
        or message.external_message_id
    )
    return str(provider_message_id)


def _send_to_channel(session: Session, message: UnifiedMessage) -> str:
    if message.channel == "whatsapp":
        return _send_whatsapp_message(session, message)

    send_url = _channel_send_url(message.channel)
    if not send_url:
        raise RuntimeError(f"Missing send URL for channel: {message.channel}")

    payload = {
        "tenant_id": message.tenant_id,
        "lead_id": message.lead_id,
        "message_id": message.id,
        "external_message_id": message.external_message_id,
        "channel_session_id": message.channel_session_id,
        "message_type": message.message_type,
        "text_content": message.text_content,
        "media_url": message.media_url,
    }

    with httpx.Client(timeout=15.0) as client:
        resp = client.post(send_url, json=payload)
        resp.raise_for_status()
        body = resp.json() if resp.content else {}
    provider_message_id = body.get("provider_message_id") or body.get("message_id") or message.external_message_id
    return str(provider_message_id)


@router.get("/channels/whatsapp/sessions", response_model=List[ChannelSession])
def list_whatsapp_sessions(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    return session.exec(
        select(ChannelSession).where(
            ChannelSession.tenant_id == auth.tenant.id,
            ChannelSession.channel_type == ChannelType.WHATSAPP,
        )
        .order_by(ChannelSession.id.asc())
    ).all()


@router.post("/channels/whatsapp/connect", response_model=WhatsAppRefreshResponse)
def connect_whatsapp_session(
    payload: WhatsAppConnectRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    session_key = _normalize_session_key(payload.session_key)
    session_identifier = f"{auth.tenant.id}:{session_key}"
    channel_session = _upsert_whatsapp_channel_session(
        session=session,
        tenant_id=auth.tenant.id,
        session_identifier=session_identifier,
        display_name=payload.display_name,
        provider_base_url=payload.provider_base_url,
    )

    base_url = _resolve_whatsapp_base_url(channel_session, payload.provider_base_url)
    endpoint = f"{base_url}/sessions/{quote(channel_session.session_identifier, safe=':')}"

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(endpoint, headers=_provider_headers())
            response.raise_for_status()
            body = response.json() if response.content else {}
    except Exception as exc:
        channel_session.status = SessionStatus.DISCONNECTED
        channel_session.updated_at = datetime.utcnow()
        meta = dict(channel_session.session_metadata or {})
        meta["last_connect_error"] = str(exc)
        channel_session.session_metadata = meta
        session.add(channel_session)
        session.commit()
        raise HTTPException(status_code=502, detail=f"WhatsApp connect failed: {str(exc)}") from exc

    channel_session.status = _map_remote_status_to_local(body.get("status"))
    channel_session.updated_at = datetime.utcnow()
    meta = dict(channel_session.session_metadata or {})
    meta["last_connect_response"] = body
    meta["last_connect_at"] = datetime.utcnow().isoformat()
    channel_session.session_metadata = meta
    session.add(channel_session)
    session.commit()
    session.refresh(channel_session)

    return WhatsAppRefreshResponse(
        channel_session_id=channel_session.id,
        session_identifier=channel_session.session_identifier,
        status=channel_session.status.value if hasattr(channel_session.status, "value") else str(channel_session.status),
        remote=body,
    )


@router.post("/channels/whatsapp/{channel_session_id}/refresh", response_model=WhatsAppRefreshResponse)
def refresh_whatsapp_session(
    channel_session_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    channel_session = _assert_whatsapp_channel_session_for_tenant(session, auth.tenant.id, channel_session_id)
    base_url = _resolve_whatsapp_base_url(channel_session)
    endpoint = f"{base_url}/sessions/{quote(channel_session.session_identifier, safe=':')}"

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(endpoint, headers=_provider_headers())
            response.raise_for_status()
            body = response.json() if response.content else {}
    except Exception as exc:
        channel_session.status = SessionStatus.DISCONNECTED
        channel_session.updated_at = datetime.utcnow()
        meta = dict(channel_session.session_metadata or {})
        meta["last_refresh_error"] = str(exc)
        channel_session.session_metadata = meta
        session.add(channel_session)
        session.commit()
        raise HTTPException(status_code=502, detail=f"WhatsApp refresh failed: {str(exc)}") from exc

    channel_session.status = _map_remote_status_to_local(body.get("status"))
    channel_session.updated_at = datetime.utcnow()
    meta = dict(channel_session.session_metadata or {})
    meta["last_refresh_response"] = body
    meta["last_refresh_at"] = datetime.utcnow().isoformat()
    channel_session.session_metadata = meta
    session.add(channel_session)
    session.commit()
    session.refresh(channel_session)

    return WhatsAppRefreshResponse(
        channel_session_id=channel_session.id,
        session_identifier=channel_session.session_identifier,
        status=channel_session.status.value if hasattr(channel_session.status, "value") else str(channel_session.status),
        remote=body,
    )


@router.get("/channels/whatsapp/{channel_session_id}/qr")
def get_whatsapp_qr(
    channel_session_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    channel_session = _assert_whatsapp_channel_session_for_tenant(session, auth.tenant.id, channel_session_id)
    base_url = _resolve_whatsapp_base_url(channel_session)
    endpoint = f"{base_url}/sessions/{quote(channel_session.session_identifier, safe=':')}/qr"

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(endpoint, headers=_provider_headers())
            if response.status_code == 404:
                return {"status": "connected_or_not_ready", "qr": None, "qrImage": None}
            response.raise_for_status()
            return response.json() if response.content else {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"WhatsApp QR fetch failed: {str(exc)}") from exc


@router.delete("/channels/whatsapp/{channel_session_id}")
def disconnect_whatsapp_session(
    channel_session_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    channel_session = _assert_whatsapp_channel_session_for_tenant(session, auth.tenant.id, channel_session_id)
    base_url = _resolve_whatsapp_base_url(channel_session)
    endpoint = f"{base_url}/sessions/{quote(channel_session.session_identifier, safe=':')}"

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.delete(endpoint, headers=_provider_headers())
            if response.status_code not in (200, 404):
                response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"WhatsApp disconnect failed: {str(exc)}") from exc

    channel_session.status = SessionStatus.DISCONNECTED
    channel_session.updated_at = datetime.utcnow()
    session.add(channel_session)
    session.commit()
    return {"status": "disconnected", "channel_session_id": channel_session.id}


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


def dispatch_next_outbound_for_tenant(session: Session, tenant_id: int) -> Optional[DispatchResponse]:
    now = datetime.utcnow()
    queue = session.exec(
        select(OutboundQueue)
        .where(
            OutboundQueue.tenant_id == tenant_id,
            OutboundQueue.status == "queued",
            OutboundQueue.next_attempt_at <= now,
        )
        .order_by(OutboundQueue.next_attempt_at.asc(), OutboundQueue.id.asc())
    ).first()

    if not queue:
        return None

    message = session.get(UnifiedMessage, queue.message_id)
    if not message or message.tenant_id != tenant_id:
        queue.status = "failed"
        queue.last_error = "Message not found or tenant mismatch"
        queue.updated_at = now
        session.add(queue)
        session.commit()
        raise HTTPException(status_code=409, detail="Queue item is invalid")

    queue.status = "dispatching"
    queue.updated_at = now
    message.delivery_status = "dispatching"
    message.updated_at = now
    session.add(queue)
    session.add(message)
    session.commit()

    try:
        provider_message_id = _send_to_channel(session, message)
        if message.channel == "whatsapp":
            queue.status = "accepted"
            message.delivery_status = "provider_accepted"
        else:
            queue.status = "sent"
            message.delivery_status = "sent"
        queue.updated_at = datetime.utcnow()
        queue.last_error = None

        message.updated_at = datetime.utcnow()
        merged_payload = dict(message.raw_payload or {})
        merged_payload["provider_message_id"] = provider_message_id
        if message.channel == "whatsapp":
            merged_payload["provider_status"] = "pending"
        message.raw_payload = merged_payload

        session.add(queue)
        session.add(message)
        session.commit()

        result = DispatchResponse(
            queue_id=queue.id,
            message_id=message.id,
            channel=message.channel,
            status=queue.status,
            retry_count=queue.retry_count,
        )
        logger.info(
            "Outbound dispatched: tenant_id=%s queue_id=%s message_id=%s channel=%s",
            tenant_id,
            queue.id,
            message.id,
            message.channel,
        )
        return result
    except Exception as exc:
        _mark_retry(queue, message, str(exc))
        session.add(queue)
        session.add(message)
        session.commit()
        logger.warning(
            "Outbound dispatch failed: tenant_id=%s queue_id=%s message_id=%s retry=%s error=%s",
            tenant_id,
            queue.id,
            message.id,
            queue.retry_count,
            str(exc),
        )
        return DispatchResponse(
            queue_id=queue.id,
            message_id=message.id,
            channel=message.channel,
            status=queue.status,
            retry_count=queue.retry_count,
            detail=str(exc),
        )
