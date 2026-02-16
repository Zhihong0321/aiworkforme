import csv
import io
import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, SQLModel, select
from sqlalchemy.exc import IntegrityError

from audit import record_admin_audit
from database import get_session
from dependencies import AuthContext, get_zai_client, require_platform_admin
from models import AdminAuditLog, Role, SecurityEventLog, SystemSetting, Tenant, TenantMembership, TenantStatus, User
from security import hash_password
from zai_client import ZaiClient


router = APIRouter(prefix="/api/v1/platform", tags=["Platform Admin"])


class TenantCreateRequest(SQLModel):
    name: str


class TenantResponse(SQLModel):
    id: int
    name: str
    status: TenantStatus
    created_at: datetime


class UserCreateRequest(SQLModel):
    email: str
    password: str
    is_platform_admin: bool = False


class UserResponse(SQLModel):
    id: int
    email: str
    is_active: bool
    is_platform_admin: bool
    created_at: datetime


class MembershipCreateRequest(SQLModel):
    user_id: int
    role: Role


class MembershipResponse(SQLModel):
    id: int
    user_id: int
    tenant_id: int
    role: Role
    is_active: bool


class TenantStatusUpdateRequest(SQLModel):
    status: TenantStatus


class UserStatusUpdateRequest(SQLModel):
    is_active: bool


class MembershipStatusUpdateRequest(SQLModel):
    is_active: bool


class AdminAuditLogResponse(SQLModel):
    id: int
    actor_user_id: int
    tenant_id: int | None
    action: str
    target_type: str
    target_id: str | None
    details: dict
    created_at: datetime


class SecurityEventLogResponse(SQLModel):
    id: int
    actor_user_id: int | None
    tenant_id: int | None
    event_type: str
    endpoint: str
    method: str
    status_code: int
    reason: str
    details: dict
    created_at: datetime


class ApiKeyRequest(SQLModel):
    api_key: str


class ApiKeyStatus(SQLModel):
    provider: str
    status: str
    masked_key: str | None = None


PROVIDER_SETTINGS = {
    "zai": ("zai_api_key", 4, 4),
    "uniapi": ("uniapi_key", 2, 2),
}


def _mask_secret(value: str, head: int, tail: int) -> str:
    if not value:
        return ""
    if len(value) <= head + tail:
        return "***"
    return f"{value[:head]}...{value[-tail:]}"


def _provider_meta(provider: str) -> tuple[str, int, int]:
    normalized = provider.strip().lower()
    meta = PROVIDER_SETTINGS.get(normalized)
    if not meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported provider")
    return meta


@router.get("/tenants", response_model=List[TenantResponse])
def list_tenants(
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    tenants = session.exec(select(Tenant).order_by(Tenant.created_at.desc())).all()
    return [
        TenantResponse(
            id=t.id,
            name=t.name,
            status=t.status,
            created_at=t.created_at,
        )
        for t in tenants
    ]


@router.post("/tenants", response_model=TenantResponse)
def create_tenant(
    payload: TenantCreateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant name is required")

    tenant = Tenant(name=name)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="tenant.create",
        target_type="tenant",
        target_id=str(tenant.id),
        tenant_id=tenant.id,
        metadata={"name": tenant.name, "status": tenant.status},
    )
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        status=tenant.status,
        created_at=tenant.created_at,
    )


@router.get("/users", response_model=List[UserResponse])
def list_users(
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    users = session.exec(select(User).order_by(User.created_at.desc())).all()
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            is_active=u.is_active,
            is_platform_admin=u.is_platform_admin,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/users", response_model=UserResponse)
def create_user(
    payload: UserCreateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")
    if len(payload.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")

    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        is_platform_admin=payload.is_platform_admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="user.create",
        target_type="user",
        target_id=str(user.id),
        metadata={"email": user.email, "is_platform_admin": user.is_platform_admin},
    )
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_platform_admin=user.is_platform_admin,
        created_at=user.created_at,
    )


@router.post("/tenants/{tenant_id}/memberships", response_model=MembershipResponse)
def create_membership(
    tenant_id: int,
    payload: MembershipCreateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    user = session.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    membership = TenantMembership(
        user_id=payload.user_id,
        tenant_id=tenant_id,
        role=payload.role,
    )
    session.add(membership)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Membership already exists",
        ) from exc

    session.refresh(membership)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="membership.create",
        target_type="tenant_membership",
        target_id=str(membership.id),
        tenant_id=tenant_id,
        metadata={"user_id": membership.user_id, "role": membership.role},
    )
    return MembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        tenant_id=membership.tenant_id,
        role=membership.role,
        is_active=membership.is_active,
    )


@router.get("/tenants/{tenant_id}/memberships", response_model=List[MembershipResponse])
def list_memberships(
    tenant_id: int,
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    memberships = session.exec(
        select(TenantMembership).where(TenantMembership.tenant_id == tenant_id)
    ).all()
    return [
        MembershipResponse(
            id=m.id,
            user_id=m.user_id,
            tenant_id=m.tenant_id,
            role=m.role,
            is_active=m.is_active,
        )
        for m in memberships
    ]


@router.patch("/tenants/{tenant_id}/status", response_model=TenantResponse)
def update_tenant_status(
    tenant_id: int,
    payload: TenantStatusUpdateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    tenant.status = payload.status
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="tenant.status.update",
        target_type="tenant",
        target_id=str(tenant.id),
        tenant_id=tenant.id,
        metadata={"status": tenant.status},
    )
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        status=tenant.status,
        created_at=tenant.created_at,
    )


@router.patch("/users/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = payload.is_active
    session.add(user)
    session.commit()
    session.refresh(user)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="user.status.update",
        target_type="user",
        target_id=str(user.id),
        metadata={"is_active": user.is_active},
    )
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_platform_admin=user.is_platform_admin,
        created_at=user.created_at,
    )


@router.patch("/tenants/{tenant_id}/memberships/{membership_id}/status", response_model=MembershipResponse)
def update_membership_status(
    tenant_id: int,
    membership_id: int,
    payload: MembershipStatusUpdateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    membership = session.exec(
        select(TenantMembership).where(
            TenantMembership.id == membership_id,
            TenantMembership.tenant_id == tenant_id,
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    membership.is_active = payload.is_active
    session.add(membership)
    session.commit()
    session.refresh(membership)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="membership.status.update",
        target_type="tenant_membership",
        target_id=str(membership.id),
        tenant_id=tenant_id,
        metadata={"is_active": membership.is_active},
    )
    return MembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        tenant_id=membership.tenant_id,
        role=membership.role,
        is_active=membership.is_active,
    )


@router.get("/audit-logs", response_model=List[AdminAuditLogResponse])
def list_audit_logs(
    tenant_id: int | None = None,
    limit: int = 100,
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    safe_limit = min(max(limit, 1), 500)
    statement = select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(safe_limit)
    if tenant_id is not None:
        statement = statement.where(AdminAuditLog.tenant_id == tenant_id)
    rows = session.exec(statement).all()
    return [
        AdminAuditLogResponse(
            id=row.id,
            actor_user_id=row.actor_user_id,
            tenant_id=row.tenant_id,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            details=row.details,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/audit-logs/export")
def export_audit_logs_csv(
    tenant_id: int | None = None,
    limit: int = 500,
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    safe_limit = min(max(limit, 1), 5000)
    statement = select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(safe_limit)
    if tenant_id is not None:
        statement = statement.where(AdminAuditLog.tenant_id == tenant_id)
    rows = session.exec(statement).all()

    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        [
            "id",
            "created_at",
            "actor_user_id",
            "tenant_id",
            "action",
            "target_type",
            "target_id",
            "details_json",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.id,
                row.created_at.isoformat() if row.created_at else "",
                row.actor_user_id,
                row.tenant_id if row.tenant_id is not None else "",
                row.action,
                row.target_type,
                row.target_id or "",
                json.dumps(row.details or {}, separators=(",", ":")),
            ]
        )

    filename = "audit-logs.csv" if tenant_id is None else f"audit-logs-tenant-{tenant_id}.csv"
    return PlainTextResponse(
        content=stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/security-events", response_model=List[SecurityEventLogResponse])
def list_security_events(
    tenant_id: int | None = None,
    limit: int = 100,
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    safe_limit = min(max(limit, 1), 500)
    statement = select(SecurityEventLog).order_by(SecurityEventLog.created_at.desc()).limit(safe_limit)
    if tenant_id is not None:
        statement = statement.where(SecurityEventLog.tenant_id == tenant_id)
    rows = session.exec(statement).all()
    return [
        SecurityEventLogResponse(
            id=row.id,
            actor_user_id=row.actor_user_id,
            tenant_id=row.tenant_id,
            event_type=row.event_type,
            endpoint=row.endpoint,
            method=row.method,
            status_code=row.status_code,
            reason=row.reason,
            details=row.details,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/api-keys", response_model=List[ApiKeyStatus])
def list_api_keys(
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    results: List[ApiKeyStatus] = []
    for provider, (setting_key, head, tail) in PROVIDER_SETTINGS.items():
        setting = session.get(SystemSetting, setting_key)
        if setting and setting.value:
            results.append(
                ApiKeyStatus(
                    provider=provider,
                    status="set",
                    masked_key=_mask_secret(setting.value, head, tail),
                )
            )
        else:
            results.append(ApiKeyStatus(provider=provider, status="not_set", masked_key=None))
    return results


@router.post("/api-keys/{provider}", response_model=ApiKeyStatus)
def upsert_api_key(
    provider: str,
    payload: ApiKeyRequest,
    session: Session = Depends(get_session),
    zai_client: ZaiClient = Depends(get_zai_client),
    context: AuthContext = Depends(require_platform_admin),
):
    setting_key, head, tail = _provider_meta(provider)
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="api_key is required")

    setting = session.get(SystemSetting, setting_key)
    action = "api_key.create"
    if not setting:
        setting = SystemSetting(key=setting_key, value=api_key)
        session.add(setting)
    else:
        setting.value = api_key
        session.add(setting)
        action = "api_key.rotate"
    session.commit()

    if setting_key == "zai_api_key":
        zai_client.update_api_key(api_key)

    masked = _mask_secret(api_key, head, tail)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action=action,
        target_type="system_setting",
        target_id=setting_key,
        metadata={"provider": provider.lower(), "masked": masked},
    )
    return ApiKeyStatus(provider=provider.lower(), status="set", masked_key=masked)


@router.delete("/api-keys/{provider}", response_model=ApiKeyStatus)
def revoke_api_key(
    provider: str,
    session: Session = Depends(get_session),
    zai_client: ZaiClient = Depends(get_zai_client),
    context: AuthContext = Depends(require_platform_admin),
):
    setting_key, _head, _tail = _provider_meta(provider)
    setting = session.get(SystemSetting, setting_key)
    if setting:
        session.delete(setting)
        session.commit()

    if setting_key == "zai_api_key":
        zai_client.update_api_key("")

    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="api_key.revoke",
        target_type="system_setting",
        target_id=setting_key,
        metadata={"provider": provider.lower()},
    )
    return ApiKeyStatus(provider=provider.lower(), status="not_set", masked_key=None)
