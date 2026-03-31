"""
MODULE: Platform Channel Routes
PURPOSE: Platform-wide messaging channel visibility for platform admins.
DOES: List channel sessions across tenants with lightweight search/filter support.
DOES NOT: Perform tenant-scoped channel lifecycle actions.
INVARIANTS: Endpoint paths and response models remain backward-compatible.
SAFE CHANGE: Add backward-compatible fields and optional filters only.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from src.adapters.api.dependencies import AuthContext, require_platform_admin
from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.tenant_models import Tenant
from src.infra.database import get_session

from .platform_schemas import PlatformChannelResponse

router = APIRouter()


def _normalize_text(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _enum_or_none(enum_type, value: Optional[str]):
    normalized = _normalize_text(value)
    if not normalized:
        return None
    try:
        return enum_type(normalized)
    except ValueError:
        return None


@router.get("/channels", response_model=List[PlatformChannelResponse])
def list_platform_channels(
    tenant_id: Optional[int] = Query(default=None),
    channel_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    statement = (
        select(ChannelSession, Tenant.name)
        .join(Tenant, Tenant.id == ChannelSession.tenant_id)
        .order_by(ChannelSession.updated_at.desc(), ChannelSession.id.desc())
    )

    normalized_channel_type = _enum_or_none(ChannelType, channel_type)
    if tenant_id is not None:
        statement = statement.where(ChannelSession.tenant_id == tenant_id)
    if normalized_channel_type:
        statement = statement.where(ChannelSession.channel_type == normalized_channel_type)

    normalized_status = _enum_or_none(SessionStatus, status)
    if normalized_status:
        statement = statement.where(ChannelSession.status == normalized_status)

    rows = session.exec(statement).all()
    search_term = _normalize_text(search)
    items: List[PlatformChannelResponse] = []

    for channel_session, tenant_name in rows:
        metadata = dict(channel_session.session_metadata or {})
        description = metadata.get("description")
        connected_number = (
            metadata.get("connected_number")
            or metadata.get("phone_number")
            or metadata.get("phone")
        )
        provider_session_id = metadata.get("provider_session_id")
        channel_type_value = (
            channel_session.channel_type.value
            if hasattr(channel_session.channel_type, "value")
            else str(channel_session.channel_type)
        )
        status_value = (
            channel_session.status.value
            if hasattr(channel_session.status, "value")
            else str(channel_session.status)
        )

        searchable_text = " ".join(
            [
                str(channel_session.id or ""),
                str(channel_session.tenant_id or ""),
                str(tenant_name or ""),
                channel_type_value,
                status_value,
                channel_session.session_identifier or "",
                channel_session.display_name or "",
                description or "",
                connected_number or "",
                provider_session_id or "",
            ]
        ).lower()
        if search_term and search_term not in searchable_text:
            continue

        items.append(
            PlatformChannelResponse(
                id=channel_session.id,
                tenant_id=channel_session.tenant_id,
                tenant_name=tenant_name,
                channel_type=channel_type_value,
                session_identifier=channel_session.session_identifier,
                display_name=channel_session.display_name,
                status=status_value,
                description=description,
                connected_number=connected_number,
                provider_session_id=provider_session_id,
                session_metadata=metadata,
                created_at=channel_session.created_at,
                updated_at=channel_session.updated_at,
            )
        )

    return items
