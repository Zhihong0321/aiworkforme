import csv
import io
import json
import time
from datetime import datetime
from typing import List, Optional

import httpx

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, SQLModel, select
from sqlalchemy.exc import IntegrityError

from src.infra.database import get_session
from src.adapters.api.dependencies import AuthContext, get_zai_client, require_platform_admin
from src.adapters.db.audit_models import AdminAuditLog, SecurityEventLog
from src.adapters.db.tenant_models import Tenant, SystemSetting
from src.adapters.db.system_settings import get_bool_system_setting
from src.adapters.db.user_models import User, TenantMembership
from src.adapters.db.messaging_models import UnifiedMessage
from src.adapters.db.crm_models import Lead
from src.domain.entities.enums import Role, TenantStatus
from src.infra.security import hash_password
from src.infra.database import engine
from src.infra.schema_checks import evaluate_message_schema_compat
from src.adapters.zai.client import ZaiClient
from src.adapters.db.audit_recorder import record_admin_audit
from src.infra.llm.schemas import LLMTask
from src.adapters.api.dependencies import refresh_llm_router_config, refresh_provider_keys_from_db


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


class PlatformMessageHistoryItem(SQLModel):
    message_id: int
    tenant_id: int
    tenant_name: str | None = None
    lead_id: int
    lead_external_id: str | None = None
    thread_id: int | None = None
    channel: str
    direction: str
    text_content: str | None = None
    delivery_status: str
    ai_generated: bool
    ai_trace: dict
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_prompt_tokens: int | None = None
    llm_completion_tokens: int | None = None
    llm_total_tokens: int | None = None
    llm_estimated_cost_usd: float | None = None
    created_at: datetime


class PlatformSystemHealthResponse(SQLModel):
    ready: bool
    checks: dict
    blockers: List[str]
    checked_at: datetime


class ApiKeyRequest(SQLModel):
    api_key: str


class ApiKeyStatus(SQLModel):
    provider: str
    status: str
    masked_key: str | None = None


class ApiKeyValidateRequest(SQLModel):
    api_key: Optional[str] = None


class ApiKeyValidationResponse(SQLModel):
    provider: str
    status: str  # valid | invalid | not_set
    detail: str
    checked_at: datetime


class LLMRoutingUpdateRequest(SQLModel):
    config: dict # Dict[str, str] where key is LLMTask value and value is provider name


class BooleanSettingResponse(SQLModel):
    key: str
    value: bool


class BooleanSettingUpdateRequest(SQLModel):
    value: bool


class BenchmarkRunItem(SQLModel):
    model: str
    provider: str
    schema: str | None = None
    run_index: int
    ok: bool
    latency_ms: int | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    error: str | None = None


class BenchmarkModelSummary(SQLModel):
    model: str
    provider: str
    schema: str | None = None
    runs: int
    success_runs: int
    failed_runs: int
    avg_latency_ms: float | None = None
    min_latency_ms: int | None = None
    max_latency_ms: int | None = None
    avg_total_tokens: float | None = None
    avg_prompt_tokens: float | None = None
    avg_completion_tokens: float | None = None


class ModelBenchmarkRequest(SQLModel):
    models: List[str]
    prompt: str = "Summarize solar lead qualification in one sentence."
    runs_per_model: int = 2
    max_tokens: int = 256
    temperature: float = 0.2
    provider: str = "uniapi"


class ModelBenchmarkResponse(SQLModel):
    provider: str
    generated_at: datetime
    prompt: str
    runs_per_model: int
    results: List[BenchmarkRunItem]
    summary: List[BenchmarkModelSummary]


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


def _validate_zai_key(api_key: str) -> tuple[bool, str]:
    url = "https://api.z.ai/api/coding/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "glm-4.7-flash",
        "messages": [{"role": "user", "content": "ping"}],
        "temperature": 0,
        "max_tokens": 1,
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                detail = resp.text[:240] if resp.text else f"HTTP {resp.status_code}"
                return False, f"Z.ai validation failed: {detail}"
            body = resp.json() if resp.content else {}
            choices = body.get("choices") if isinstance(body, dict) else None
            if not choices:
                return False, "Z.ai key check returned no choices"
            return True, "Z.ai key is valid"
    except Exception as exc:
        return False, f"Z.ai validation error: {str(exc)}"


def _validate_uniapi_key(api_key: str) -> tuple[bool, str]:
    url = "https://api.uniapi.io/gemini/v1beta/models/gemini-3-flash-preview:generateContent"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "ping"}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 1},
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                detail = resp.text[:240] if resp.text else f"HTTP {resp.status_code}"
                return False, f"UniAPI validation failed: {detail}"
            body = resp.json() if resp.content else {}
            candidates = body.get("candidates") if isinstance(body, dict) else None
            if not candidates:
                return False, "UniAPI key check returned no candidates"
            return True, "UniAPI key is valid"
    except Exception as exc:
        return False, f"UniAPI validation error: {str(exc)}"


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


@router.get("/messages/history", response_model=List[PlatformMessageHistoryItem])
def list_platform_message_history(
    limit: int = 200,
    tenant_id: int | None = None,
    direction: str | None = None,
    ai_only: bool = False,
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    safe_limit = min(max(limit, 1), 1000)
    statement = select(UnifiedMessage).order_by(UnifiedMessage.created_at.desc()).limit(safe_limit)
    if tenant_id is not None:
        statement = statement.where(UnifiedMessage.tenant_id == tenant_id)
    if direction in {"inbound", "outbound"}:
        statement = statement.where(UnifiedMessage.direction == direction)

    rows = session.exec(statement).all()
    if ai_only:
        rows = [
            row for row in rows
            if (
                isinstance(row.raw_payload, dict) and isinstance(row.raw_payload.get("ai_trace"), dict)
            ) or bool(row.llm_provider)
        ]

    tenant_ids = {row.tenant_id for row in rows}
    lead_ids = {row.lead_id for row in rows}

    tenants = session.exec(select(Tenant).where(Tenant.id.in_(tenant_ids))).all() if tenant_ids else []
    leads = session.exec(select(Lead).where(Lead.id.in_(lead_ids))).all() if lead_ids else []
    tenant_map = {t.id: t.name for t in tenants}
    lead_map = {l.id: l.external_id for l in leads}

    results: List[PlatformMessageHistoryItem] = []
    for row in rows:
        payload = row.raw_payload if isinstance(row.raw_payload, dict) else {}
        ai_trace = payload.get("ai_trace") if isinstance(payload.get("ai_trace"), dict) else {}
        ai_generated = bool(ai_trace) or bool(row.llm_provider)
        results.append(
            PlatformMessageHistoryItem(
                message_id=row.id,
                tenant_id=row.tenant_id,
                tenant_name=tenant_map.get(row.tenant_id),
                lead_id=row.lead_id,
                lead_external_id=lead_map.get(row.lead_id),
                thread_id=row.thread_id,
                channel=row.channel,
                direction=row.direction,
                text_content=row.text_content,
                delivery_status=row.delivery_status,
                ai_generated=ai_generated,
                ai_trace=ai_trace,
                llm_provider=row.llm_provider,
                llm_model=row.llm_model,
                llm_prompt_tokens=row.llm_prompt_tokens,
                llm_completion_tokens=row.llm_completion_tokens,
                llm_total_tokens=row.llm_total_tokens,
                llm_estimated_cost_usd=row.llm_estimated_cost_usd,
                created_at=row.created_at,
            )
        )
    return results


@router.get("/system-health", response_model=PlatformSystemHealthResponse)
def get_platform_system_health(
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    checks: dict = {}
    blockers: List[str] = []

    schema_check = evaluate_message_schema_compat(engine)
    checks["schema"] = schema_check
    if not schema_check.get("ok"):
        blockers.append(
            f"Schema incompatible for et_messages. Missing columns: {schema_check.get('missing_columns', [])}"
        )

    from src.app.background_tasks_inbound import get_inbound_worker_debug_snapshot
    checks["inbound_worker"] = get_inbound_worker_debug_snapshot()

    from src.adapters.api.dependencies import llm_router
    provider_health = {}
    for provider_name, provider in llm_router.providers.items():
        try:
            provider_health[provider_name] = bool(provider.is_healthy())
        except Exception:
            provider_health[provider_name] = False
    checks["llm_provider_health"] = provider_health

    pending_inbound = session.exec(
        select(UnifiedMessage)
        .where(
            UnifiedMessage.direction == "inbound",
            UnifiedMessage.delivery_status == "received",
        )
        .limit(1)
    ).first()
    checks["inbound_backlog_present"] = bool(pending_inbound)

    return PlatformSystemHealthResponse(
        ready=len(blockers) == 0,
        checks=checks,
        blockers=blockers,
        checked_at=datetime.utcnow(),
    )


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

    refresh_provider_keys_from_db(session)

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

    refresh_provider_keys_from_db(session)

    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="api_key.revoke",
        target_type="system_setting",
        target_id=setting_key,
        metadata={"provider": provider.lower()},
    )
    return ApiKeyStatus(provider=provider.lower(), status="not_set", masked_key=None)


@router.post("/api-keys/{provider}/validate", response_model=ApiKeyValidationResponse)
def validate_api_key(
    provider: str,
    payload: ApiKeyValidateRequest,
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    setting_key, _head, _tail = _provider_meta(provider)
    input_key = (payload.api_key or "").strip()
    if input_key:
        api_key = input_key
    else:
        setting = session.get(SystemSetting, setting_key)
        api_key = (setting.value if setting and setting.value else "").strip()

    checked_at = datetime.utcnow()
    if not api_key:
        return ApiKeyValidationResponse(
            provider=provider.lower(),
            status="not_set",
            detail="No key to validate. Enter one or save it first.",
            checked_at=checked_at,
        )

    normalized = provider.strip().lower()
    if normalized == "zai":
        is_valid, detail = _validate_zai_key(api_key)
    elif normalized == "uniapi":
        is_valid, detail = _validate_uniapi_key(api_key)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported provider")

    return ApiKeyValidationResponse(
        provider=normalized,
        status="valid" if is_valid else "invalid",
        detail=detail,
        checked_at=checked_at,
    )

@router.get("/llm/routing")
def get_llm_routing(
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    setting = session.get(SystemSetting, "llm_routing_config")
    if setting and setting.value:
        return json.loads(setting.value)
    
    # Return default from code if not in DB
    from src.adapters.api.dependencies import llm_router
    return {k.value: v for k, v in llm_router.routing_config.items()}

@router.post("/llm/routing")
def update_llm_routing(
    payload: LLMRoutingUpdateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    # Validate tasks
    valid_tasks = {t.value for t in LLMTask}
    for task in payload.config.keys():
        if task not in valid_tasks:
            raise HTTPException(status_code=400, detail=f"Invalid LLM task: {task}")
    
    # Save to DB
    setting = session.get(SystemSetting, "llm_routing_config")
    if not setting:
        setting = SystemSetting(key="llm_routing_config", value=json.dumps(payload.config))
    else:
        setting.value = json.dumps(payload.config)
    
    session.add(setting)
    session.commit()
    
    # Refresh router
    refresh_llm_router_config(session)
    
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="llm_routing.update",
        target_type="system_setting",
        target_id="llm_routing_config",
        metadata={"config": payload.config},
    )
    
    return {"status": "updated", "config": payload.config}

@router.get("/llm/providers")
def list_llm_providers(
    _context: AuthContext = Depends(require_platform_admin),
):
    from src.adapters.api.dependencies import llm_router
    return list(llm_router.providers.keys())

@router.get("/llm/tasks")
def list_llm_tasks(
    _context: AuthContext = Depends(require_platform_admin),
):
    return [t.value for t in LLMTask]


@router.get("/llm/models")
def list_llm_models(
    _context: AuthContext = Depends(require_platform_admin),
):
    from src.adapters.api.dependencies import llm_router

    results: List[dict] = []
    for provider_name, provider in llm_router.providers.items():
        if hasattr(provider, "list_supported_models"):
            try:
                items = provider.list_supported_models()
                if isinstance(items, list):
                    results.extend(items)
            except Exception:
                continue
        else:
            results.append({"provider": provider_name, "model": "dynamic", "schema": "runtime"})
    return results


@router.post("/llm/benchmark", response_model=ModelBenchmarkResponse)
async def benchmark_llm_models(
    payload: ModelBenchmarkRequest,
    _context: AuthContext = Depends(require_platform_admin),
):
    from src.adapters.api.dependencies import llm_router

    provider_name = (payload.provider or "").strip().lower() or "uniapi"
    if provider_name not in llm_router.providers:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_name}")

    provider = llm_router.providers.get(provider_name)
    if not provider or not provider.is_healthy():
        raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' is not configured")

    models = [m.strip() for m in (payload.models or []) if isinstance(m, str) and m.strip()]
    if not models:
        raise HTTPException(status_code=400, detail="At least one model is required")

    runs_per_model = min(max(int(payload.runs_per_model or 1), 1), 20)
    prompt = (payload.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    max_tokens = min(max(int(payload.max_tokens or 64), 1), 4096)
    temperature = float(payload.temperature if payload.temperature is not None else 0.2)
    if temperature < 0:
        temperature = 0
    if temperature > 2:
        temperature = 2

    run_results: List[BenchmarkRunItem] = []
    summary_map: dict[str, dict] = {}

    for model in models:
        for run_index in range(1, runs_per_model + 1):
            t0 = time.perf_counter()
            try:
                response = await llm_router.execute(
                    task=LLMTask.CONVERSATION,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=model,
                    provider=provider_name,
                    disable_fallback=True,
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                usage = response.usage or {}
                prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
                completion_tokens = int(usage.get("completion_tokens", 0) or 0)
                total_tokens = int(usage.get("total_tokens", 0) or (prompt_tokens + completion_tokens))
                provider_info = response.provider_info or {}
                schema = provider_info.get("schema")

                row = BenchmarkRunItem(
                    model=model,
                    provider=provider_info.get("provider") or provider_name,
                    schema=schema,
                    run_index=run_index,
                    ok=True,
                    latency_ms=latency_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
            except Exception as exc:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                row = BenchmarkRunItem(
                    model=model,
                    provider=provider_name,
                    schema=None,
                    run_index=run_index,
                    ok=False,
                    latency_ms=latency_ms,
                    error=str(exc),
                )
            run_results.append(row)

            key = f"{row.provider}|{row.model}|{row.schema or ''}"
            bucket = summary_map.setdefault(
                key,
                {
                    "model": row.model,
                    "provider": row.provider,
                    "schema": row.schema,
                    "runs": 0,
                    "success_runs": 0,
                    "failed_runs": 0,
                    "latencies": [],
                    "prompt_tokens": [],
                    "completion_tokens": [],
                    "total_tokens": [],
                },
            )
            bucket["runs"] += 1
            if row.ok:
                bucket["success_runs"] += 1
                if row.latency_ms is not None:
                    bucket["latencies"].append(row.latency_ms)
                bucket["prompt_tokens"].append(row.prompt_tokens)
                bucket["completion_tokens"].append(row.completion_tokens)
                bucket["total_tokens"].append(row.total_tokens)
            else:
                bucket["failed_runs"] += 1

    summaries: List[BenchmarkModelSummary] = []
    for item in summary_map.values():
        latencies = item["latencies"]
        prompt_tokens = item["prompt_tokens"]
        completion_tokens = item["completion_tokens"]
        total_tokens = item["total_tokens"]
        summaries.append(
            BenchmarkModelSummary(
                model=item["model"],
                provider=item["provider"],
                schema=item["schema"],
                runs=item["runs"],
                success_runs=item["success_runs"],
                failed_runs=item["failed_runs"],
                avg_latency_ms=(sum(latencies) / len(latencies)) if latencies else None,
                min_latency_ms=min(latencies) if latencies else None,
                max_latency_ms=max(latencies) if latencies else None,
                avg_total_tokens=(sum(total_tokens) / len(total_tokens)) if total_tokens else None,
                avg_prompt_tokens=(sum(prompt_tokens) / len(prompt_tokens)) if prompt_tokens else None,
                avg_completion_tokens=(sum(completion_tokens) / len(completion_tokens)) if completion_tokens else None,
            )
        )

    summaries.sort(
        key=lambda x: (
            x.avg_latency_ms if x.avg_latency_ms is not None else float("inf"),
            -(x.success_runs or 0),
        )
    )

    return ModelBenchmarkResponse(
        provider=provider_name,
        generated_at=datetime.utcnow(),
        prompt=prompt,
        runs_per_model=runs_per_model,
        results=run_results,
        summary=summaries,
    )


@router.get("/settings/record-context-prompt", response_model=BooleanSettingResponse)
def get_record_context_prompt_setting(
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    value = get_bool_system_setting(session, "record_context_prompt", default=False)
    return BooleanSettingResponse(key="record_context_prompt", value=value)


@router.put("/settings/record-context-prompt", response_model=BooleanSettingResponse)
def upsert_record_context_prompt_setting(
    payload: BooleanSettingUpdateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    setting = session.get(SystemSetting, "record_context_prompt")
    value_as_string = "true" if payload.value else "false"
    if not setting:
        setting = SystemSetting(key="record_context_prompt", value=value_as_string)
    else:
        setting.value = value_as_string

    session.add(setting)
    session.commit()

    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="platform_setting.update",
        target_type="system_setting",
        target_id="record_context_prompt",
        metadata={"value": payload.value},
    )
    return BooleanSettingResponse(key="record_context_prompt", value=payload.value)
