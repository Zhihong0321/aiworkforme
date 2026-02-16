from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import SQLModel, Session, select

from database import get_session
from dependencies import AuthContext, require_tenant_access
from models import Agent, ChatMessageNew, ConversationThread, Lead, PolicyDecision, SecurityEventLog, Workspace


router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


class TelemetrySummaryResponse(SQLModel):
    generated_at: datetime
    window_hours: int
    workspace_count: int
    agent_count: int
    lead_count: int
    thread_count: int
    message_count: int
    policy_decisions_window: int
    policy_blocks_window: int
    denied_events_window: int


class SecurityEventResponse(SQLModel):
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


def _bounded_limit(limit: int) -> int:
    return min(max(limit, 1), 500)


def _bounded_hours(window_hours: int) -> int:
    return min(max(window_hours, 1), 24 * 14)


@router.get("/summary", response_model=TelemetrySummaryResponse)
def summary(
    window_hours: int = 24,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_tenant_access),
):
    tenant_id = context.tenant.id
    safe_window_hours = _bounded_hours(window_hours)
    window_start = datetime.utcnow() - timedelta(hours=safe_window_hours)

    workspace_count = int(
        session.exec(
            select(func.count(Workspace.id)).where(Workspace.tenant_id == tenant_id)
        ).one()
    )
    agent_count = int(
        session.exec(select(func.count(Agent.id)).where(Agent.tenant_id == tenant_id)).one()
    )
    lead_count = int(
        session.exec(select(func.count(Lead.id)).where(Lead.tenant_id == tenant_id)).one()
    )
    thread_count = int(
        session.exec(
            select(func.count(ConversationThread.id)).where(ConversationThread.tenant_id == tenant_id)
        ).one()
    )
    message_count = int(
        session.exec(
            select(func.count(ChatMessageNew.id)).where(ChatMessageNew.tenant_id == tenant_id)
        ).one()
    )
    policy_decisions_window = int(
        session.exec(
            select(func.count(PolicyDecision.id)).where(
                PolicyDecision.tenant_id == tenant_id,
                PolicyDecision.created_at >= window_start,
            )
        ).one()
    )
    policy_blocks_window = int(
        session.exec(
            select(func.count(PolicyDecision.id)).where(
                PolicyDecision.tenant_id == tenant_id,
                PolicyDecision.allow_send == False,  # noqa: E712
                PolicyDecision.created_at >= window_start,
            )
        ).one()
    )
    denied_events_window = int(
        session.exec(
            select(func.count(SecurityEventLog.id)).where(
                SecurityEventLog.tenant_id == tenant_id,
                SecurityEventLog.event_type == "access.denied",
                SecurityEventLog.created_at >= window_start,
            )
        ).one()
    )

    return TelemetrySummaryResponse(
        generated_at=datetime.utcnow(),
        window_hours=safe_window_hours,
        workspace_count=workspace_count,
        agent_count=agent_count,
        lead_count=lead_count,
        thread_count=thread_count,
        message_count=message_count,
        policy_decisions_window=policy_decisions_window,
        policy_blocks_window=policy_blocks_window,
        denied_events_window=denied_events_window,
    )


@router.get("/security-events", response_model=List[SecurityEventResponse])
def tenant_security_events(
    limit: int = 100,
    window_hours: int = 24,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_tenant_access),
):
    tenant_id = context.tenant.id
    safe_limit = _bounded_limit(limit)
    safe_window_hours = _bounded_hours(window_hours)
    window_start = datetime.utcnow() - timedelta(hours=safe_window_hours)

    rows = session.exec(
        select(SecurityEventLog)
        .where(
            SecurityEventLog.tenant_id == tenant_id,
            SecurityEventLog.created_at >= window_start,
        )
        .order_by(SecurityEventLog.created_at.desc())
        .limit(safe_limit)
    ).all()
    return [
        SecurityEventResponse(
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
