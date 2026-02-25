"""
MODULE: Messaging Validation Helpers
PURPOSE: Validation, lookup, and session/thread helper functions for messaging routes.
DOES: Entity/session verification and canonical thread resolution.
DOES NOT: Parse provider payload structures.
INVARIANTS: Validation error semantics remain stable.
SAFE CHANGE: Keep error codes/messages compatible.
"""

import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from src.adapters.db.agent_models import Agent
from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.messaging_models import OutboundQueue, UnifiedMessage, UnifiedThread
from src.app.runtime.leads_service import get_or_create_default_workspace


def validate_lead_tenant(session: Session, lead_id: int, tenant_id: int) -> Lead:
    lead = session.get(Lead, lead_id)
    if not lead or lead.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


def stage_value(stage) -> str:
    return stage.value if hasattr(stage, "value") else str(stage)


def validate_channel_session(
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

    channel_type = (
        channel_session.channel_type.value
        if hasattr(channel_session.channel_type, "value")
        else channel_session.channel_type
    )
    if str(channel_type) != channel:
        raise HTTPException(status_code=400, detail="Channel session does not match channel")

    return channel_session


def resolve_agent_for_lead(session: Session, tenant_id: int, lead_id: int) -> int:
    lead = session.get(Lead, lead_id)
    if not lead or lead.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    workspace = session.get(Workspace, lead.workspace_id)
    if workspace and workspace.tenant_id == tenant_id and workspace.agent_id is not None:
        agent = session.get(Agent, workspace.agent_id)
        if agent and agent.tenant_id == tenant_id:
            return agent.id

    fallback_agent = (
        session.exec(select(Agent).where(Agent.tenant_id == tenant_id).order_by(Agent.id.asc())).first()
    )
    if fallback_agent:
        return fallback_agent.id

    raise HTTPException(
        status_code=400,
        detail="No AI agent is configured for tenant. Configure at least one agent first.",
    )


def get_or_create_thread(session: Session, tenant_id: int, lead_id: int, channel: str) -> UnifiedThread:
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
            thread.agent_id = resolve_agent_for_lead(session, tenant_id, lead_id)
            thread.updated_at = datetime.utcnow()
            session.add(thread)
            session.commit()
            session.refresh(thread)
        return thread

    agent_id = resolve_agent_for_lead(session, tenant_id, lead_id)
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


def provider_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    api_key = os.getenv("WHATSAPP_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def normalize_session_key(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", (value or "").strip()).strip("-").lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="session_key is required")
    if len(normalized) > 64:
        raise HTTPException(status_code=400, detail="session_key is too long (max 64)")
    return normalized


def resolve_whatsapp_base_url(
    channel_session: Optional[ChannelSession] = None, override_url: Optional[str] = None
) -> str:
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


def extract_whatsapp_recipient(lead_external_id: Optional[str]) -> str:
    if not lead_external_id:
        raise RuntimeError("Lead external_id is required for WhatsApp send")

    raw = str(lead_external_id).strip()
    if "@s.whatsapp.net" in raw:
        return raw.split("@", 1)[0]

    digits = re.sub(r"\D+", "", raw)
    if not digits:
        raise RuntimeError("Lead external_id has no valid WhatsApp number")
    return digits


def validate_lead_number_for_whatsapp(lead: Lead) -> str:
    recipient = extract_whatsapp_recipient(lead.external_id)
    if not (8 <= len(recipient) <= 15):
        raise HTTPException(
            status_code=400,
            detail="Lead external_id must be a valid WhatsApp number (8-15 digits with country code).",
        )
    return recipient


def upsert_whatsapp_channel_session(
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


def assert_whatsapp_channel_session_for_tenant(
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


def map_remote_status_to_local(remote_status: Optional[str]) -> SessionStatus:
    value = str(remote_status or "").strip().lower()
    if value in {"connected", "active", "live", "ready"}:
        return SessionStatus.ACTIVE
    return SessionStatus.DISCONNECTED


def channel_send_url(channel: str) -> Optional[str]:
    mapping = {
        "email": os.getenv("EMAIL_CHANNEL_SEND_URL"),
        "telegram": os.getenv("TELEGRAM_CHANNEL_SEND_URL"),
    }
    return mapping.get(channel)


def mark_retry(queue: OutboundQueue, message: UnifiedMessage, err: str):
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


def resolve_whatsapp_channel_session_for_tenant(
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


def _digits_only(value: Optional[str]) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _phone_lookup_keys(value: Optional[str]) -> List[str]:
    digits = _digits_only(value)
    if not digits:
        return []

    keys: List[str] = []
    seen: set[str] = set()

    def add(v: Optional[str]) -> None:
        if not v:
            return
        key = str(v).strip()
        if not key or key in seen:
            return
        seen.add(key)
        keys.append(key)

    add(digits)
    add(f"+{digits}")
    add(f"whatsapp:{digits}")
    add(f"whatsapp:+{digits}")
    if digits.startswith("0") and len(digits) >= 9:
        add("6" + digits)
        add("+6" + digits)
    if digits.startswith("60") and len(digits) >= 10:
        local = "0" + digits[2:]
        add(local)
        add("+" + local)
    return keys


def _channel_session_matches_phone(channel_session: ChannelSession, phone: Optional[str]) -> bool:
    if not phone:
        return True
    phone_digits = _digits_only(phone)
    if not phone_digits:
        return True

    candidates: List[str] = [channel_session.session_identifier, channel_session.display_name or ""]
    metadata = channel_session.session_metadata if isinstance(channel_session.session_metadata, dict) else {}
    for key in (
        "phone",
        "phone_number",
        "whatsapp_number",
        "wa_phone",
        "wid",
        "jid",
        "session_phone",
        "connected_number",
    ):
        value = metadata.get(key)
        if isinstance(value, str):
            candidates.append(value)

    me_obj = metadata.get("me")
    if isinstance(me_obj, dict):
        for key in ("id", "jid", "phone", "number"):
            value = me_obj.get(key)
            if isinstance(value, str):
                candidates.append(value)

    for raw in candidates:
        raw_digits = _digits_only(raw)
        if not raw_digits:
            continue
        if raw_digits.endswith(phone_digits) or phone_digits.endswith(raw_digits):
            return True
    return False


def resolve_whatsapp_channel_session_by_phone(
    session: Session,
    tenant_id: int,
    channel_session_id: Optional[int],
    tenant_whatsapp_phone: Optional[str],
) -> Optional[ChannelSession]:
    if channel_session_id is not None:
        channel_session = validate_channel_session(session, tenant_id, "whatsapp", channel_session_id)
        if channel_session and tenant_whatsapp_phone and not _channel_session_matches_phone(
            channel_session, tenant_whatsapp_phone
        ):
            raise HTTPException(
                status_code=400,
                detail="channel_session_id does not match recipient/sender WhatsApp phone",
            )
        return channel_session

    sessions = session.exec(
        select(ChannelSession).where(
            ChannelSession.tenant_id == tenant_id,
            ChannelSession.channel_type == ChannelType.WHATSAPP,
        )
    ).all()
    if not sessions:
        return None

    if not tenant_whatsapp_phone:
        active = [s for s in sessions if s.status == SessionStatus.ACTIVE]
        if len(active) == 1:
            return active[0]
        if len(sessions) == 1:
            return sessions[0]
        return None

    matching = [s for s in sessions if _channel_session_matches_phone(s, tenant_whatsapp_phone)]
    if len(matching) == 1:
        return matching[0]
    if len(matching) > 1:
        active = [s for s in matching if s.status == SessionStatus.ACTIVE]
        if len(active) == 1:
            return active[0]
        return None

    active = [s for s in sessions if s.status == SessionStatus.ACTIVE]
    if len(active) == 1:
        return active[0]
    if len(sessions) == 1:
        return sessions[0]
    return None


def resolve_or_create_whatsapp_lead_by_phone(
    session: Session,
    tenant_id: int,
    lead_phone: str,
) -> Lead:
    phone_keys = _phone_lookup_keys(lead_phone)
    if not phone_keys:
        raise HTTPException(status_code=400, detail="Lead phone number is required for WhatsApp mapping")

    candidates = session.exec(
        select(Lead).where(
            Lead.tenant_id == tenant_id,
        )
    ).all()
    by_id: Dict[int, Lead] = {}
    for lead in candidates:
        lead_keys = _phone_lookup_keys(lead.external_id)
        if lead.whatsapp_lid:
            lead_keys.extend(_phone_lookup_keys(lead.whatsapp_lid))
        if any(k in lead_keys for k in phone_keys):
            if lead.id is not None:
                by_id[lead.id] = lead

    if by_id:
        if len(by_id) == 1:
            return next(iter(by_id.values()))

        recent = session.exec(
            select(UnifiedMessage.lead_id)
            .where(
                UnifiedMessage.tenant_id == tenant_id,
                UnifiedMessage.channel == "whatsapp",
                UnifiedMessage.lead_id.in_(list(by_id.keys())),
            )
            .order_by(UnifiedMessage.created_at.desc(), UnifiedMessage.id.desc())
        ).first()
        if recent in by_id:
            return by_id[recent]
        return sorted(by_id.values(), key=lambda item: int(item.id or 0))[0]

    primary = _digits_only(lead_phone)
    workspace = get_or_create_default_workspace(session, tenant_id)
    new_lead = Lead(
        tenant_id=tenant_id,
        workspace_id=workspace.id,
        external_id=primary,
        name=None,
        stage="CONTACTED",
        tags=[],
        is_whatsapp_valid=bool(8 <= len(primary) <= 15),
        created_at=datetime.utcnow(),
    )
    session.add(new_lead)
    session.commit()
    session.refresh(new_lead)
    return new_lead
