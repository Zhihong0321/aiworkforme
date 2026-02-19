from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import SQLModel, Session, select

from src.infra.database import get_session
from src.adapters.api.dependencies import AuthContext, require_tenant_access
from src.adapters.db.agent_models import Agent
from src.adapters.db.crm_models import ChatMessageNew, ConversationThread, Lead, PolicyDecision, Workspace
from src.adapters.db.audit_models import SecurityEventLog
from src.adapters.db.messaging_models import UnifiedMessage
from src.infra.llm.costs import estimate_llm_cost_usd


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
    llm_cost_window: dict


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


def _safe_int(value: int | None) -> int:
    return int(value or 0)


def _safe_float(value: float | None) -> float:
    return float(value or 0.0)


def _compute_llm_cost_window(session: Session, tenant_id: int, window_start: datetime) -> dict:
    rows = session.exec(
        select(
            UnifiedMessage.llm_provider,
            UnifiedMessage.llm_model,
            UnifiedMessage.llm_prompt_tokens,
            UnifiedMessage.llm_completion_tokens,
            UnifiedMessage.llm_total_tokens,
            UnifiedMessage.llm_estimated_cost_usd,
        ).where(
            UnifiedMessage.tenant_id == tenant_id,
            UnifiedMessage.created_at >= window_start,
            UnifiedMessage.llm_model.is_not(None),
        )
    ).all()

    per_model: dict[str, dict] = {}
    for row in rows:
        provider = (row[0] or "unknown").strip() or "unknown"
        model = (row[1] or "unknown").strip() or "unknown"
        prompt_tokens = _safe_int(row[2])
        completion_tokens = _safe_int(row[3])
        total_tokens = _safe_int(row[4])
        if total_tokens <= 0:
            total_tokens = prompt_tokens + completion_tokens
        total_cost_usd = _safe_float(row[5])
        if total_cost_usd <= 0 and total_tokens > 0:
            total_cost_usd = estimate_llm_cost_usd(
                provider=provider,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

        bucket_key = f"{provider}|{model}"
        bucket = per_model.setdefault(
            bucket_key,
            {
                "model": model,
                "provider": provider,
                "message_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
            },
        )
        bucket["message_count"] += 1
        bucket["prompt_tokens"] += prompt_tokens
        bucket["completion_tokens"] += completion_tokens
        bucket["total_tokens"] += total_tokens
        bucket["total_cost_usd"] += total_cost_usd

    models: List[dict] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    total_cost_usd = 0.0
    for model_bucket in per_model.values():
        model_total_tokens = int(model_bucket["total_tokens"] or 0)
        model_total_cost = float(model_bucket["total_cost_usd"] or 0.0)
        cost_per_token = (model_total_cost / model_total_tokens) if model_total_tokens > 0 else 0.0
        model_bucket["total_cost_usd"] = round(model_total_cost, 6)
        model_bucket["cost_per_token_usd"] = round(cost_per_token, 12)
        model_bucket["cost_per_1m_tokens_usd"] = round(cost_per_token * 1_000_000.0, 6)
        models.append(model_bucket)

        total_prompt_tokens += int(model_bucket["prompt_tokens"] or 0)
        total_completion_tokens += int(model_bucket["completion_tokens"] or 0)
        total_tokens += model_total_tokens
        total_cost_usd += model_total_cost

    models.sort(key=lambda item: item["total_cost_usd"], reverse=True)
    global_cost_per_token = (total_cost_usd / total_tokens) if total_tokens > 0 else 0.0
    return {
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost_usd, 6),
        "cost_per_token_usd": round(global_cost_per_token, 12),
        "cost_per_1m_tokens_usd": round(global_cost_per_token * 1_000_000.0, 6),
        "models": models,
    }


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
    llm_cost_window = _compute_llm_cost_window(session, tenant_id, window_start)

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
        llm_cost_window=llm_cost_window,
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
