"""
MODULE: Messaging WhatsApp Routes
PURPOSE: WhatsApp session lifecycle and import endpoints for unified messaging.
DOES: Handle connect/refresh/QR/disconnect operations and import command endpoint.
DOES NOT: Handle inbound/outbound generic messaging flows.
INVARIANTS: Endpoint paths and response payloads remain backward-compatible.
SAFE CHANGE: Keep provider request contracts unchanged.
"""

import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from src.adapters.api.dependencies import AuthContext, require_tenant_access
from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.messaging_models import UnifiedMessage
from src.infra.database import get_session

from .messaging_helpers import (
    assert_whatsapp_channel_session_for_tenant as _assert_whatsapp_channel_session_for_tenant,
    chat_display_name as _chat_display_name,
    chat_jid as _chat_jid,
    chat_phone_number as _chat_phone_number,
    extract_list as _extract_list,
    map_remote_status_to_local as _map_remote_status_to_local,
    message_direction as _message_direction,
    message_external_id as _message_external_id,
    message_raw_payload as _message_raw_payload,
    message_text as _message_text,
    message_timestamp as _message_timestamp,
    message_type as _message_type,
    name_confidence_score as _name_confidence_score,
    normalize_seed_phone as _normalize_seed_phone,
    normalize_session_key as _normalize_session_key,
    normalize_whatsapp_external_id_from_jid as _normalize_whatsapp_external_id_from_jid,
    phone_match_keys as _phone_match_keys,
    provider_headers as _provider_headers,
    resolve_whatsapp_base_url as _resolve_whatsapp_base_url,
    resolve_whatsapp_channel_session_for_tenant as _resolve_whatsapp_channel_session_for_tenant,
    upsert_whatsapp_channel_session as _upsert_whatsapp_channel_session,
    get_or_create_thread as _get_or_create_thread,
)
from .messaging_schemas import (
    WhatsAppConnectRequest,
    WhatsAppConversationImportRequest,
    WhatsAppConversationImportResponse,
    WhatsAppRefreshResponse,
)

router = APIRouter()

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


