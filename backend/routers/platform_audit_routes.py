"""
MODULE: Platform Audit And Health Routes
PURPOSE: Audit exports, security event feeds, message history, and health endpoints.
DOES: Read-only administrative visibility operations for platform admins.
DOES NOT: Mutate identity records or provider key settings.
INVARIANTS: Export format and endpoint semantics remain stable.
SAFE CHANGE: Add new read-only fields without removing existing ones.
"""

import csv
import io
import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, select

from src.adapters.api.dependencies import AuthContext, require_platform_admin
from src.adapters.db.audit_models import AdminAuditLog, SecurityEventLog
from src.adapters.db.crm_models import Lead
from src.adapters.db.messaging_models import UnifiedMessage
from src.adapters.db.tenant_models import Tenant
from src.infra.database import engine, get_session
from src.infra.schema_checks import evaluate_message_schema_compat

from .platform_schemas import (
    AdminAuditLogResponse,
    PlatformMessageHistoryItem,
    PlatformSystemHealthResponse,
    SecurityEventLogResponse,
)

router = APIRouter()


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
            row
            for row in rows
            if (
                isinstance(row.raw_payload, dict) and isinstance(row.raw_payload.get("ai_trace"), dict)
            )
            or bool(row.llm_provider)
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
