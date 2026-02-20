"""
MODULE: AI CRM Routes
PURPOSE: HTTP handlers for AI CRM control, thread listing, scan, and trigger endpoints.
DOES: Validate request scope and delegate workflow operations to helper/runtime modules.
DOES NOT: Implement background cycle orchestration internals.
INVARIANTS: Endpoint paths and response models remain stable.
SAFE CHANGE: Keep delegation boundaries explicit and behavior-preserving.
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from src.adapters.api.dependencies import AuthContext, get_llm_router, require_tenant_access
from src.adapters.db.crm_models import Lead
from src.adapters.db.messaging_models import UnifiedMessage, UnifiedThread
from src.infra.database import get_session
from src.infra.llm.router import LLMRouter

from .ai_crm_helpers import (
    as_control_response,
    ensure_control,
    normalize_aggressiveness,
    normalize_strategy,
    upsert_thread_state,
    validate_workspace,
)
from .ai_crm_runtime import scan_workspace_threads, trigger_due_followups
from .ai_crm_schemas import (
    AICRMControlResponse,
    AICRMControlUpdateRequest,
    AICRMScanRequest,
    AICRMScanResponse,
    AICRMThreadRow,
    AICRMTriggerResponse,
)

router = APIRouter()


@router.get("/{workspace_id}/ai-crm/control", response_model=AICRMControlResponse)
def get_ai_crm_control(
    workspace_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    validate_workspace(session, auth.tenant.id, workspace_id)
    control = ensure_control(session, auth.tenant.id, workspace_id)
    return as_control_response(control)


@router.put("/{workspace_id}/ai-crm/control", response_model=AICRMControlResponse)
def update_ai_crm_control(
    workspace_id: int,
    payload: AICRMControlUpdateRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    validate_workspace(session, auth.tenant.id, workspace_id)
    if payload.scan_frequency_messages < 3 or payload.scan_frequency_messages > 10:
        raise HTTPException(status_code=400, detail="scan_frequency_messages must be between 3 and 10")

    control = ensure_control(session, auth.tenant.id, workspace_id)
    control.enabled = bool(payload.enabled)
    control.scan_frequency_messages = int(payload.scan_frequency_messages)
    control.aggressiveness = normalize_aggressiveness(payload.aggressiveness)
    control.not_interested_strategy = normalize_strategy(payload.not_interested_strategy)
    control.rejected_strategy = normalize_strategy(payload.rejected_strategy)
    control.double_reject_strategy = normalize_strategy(payload.double_reject_strategy)
    control.updated_at = datetime.utcnow()

    session.add(control)
    session.commit()
    session.refresh(control)
    return as_control_response(control)


@router.get("/{workspace_id}/ai-crm/threads", response_model=List[AICRMThreadRow])
def list_ai_crm_threads(
    workspace_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    validate_workspace(session, auth.tenant.id, workspace_id)
    control = ensure_control(session, auth.tenant.id, workspace_id)
    threshold = max(3, min(10, int(control.scan_frequency_messages or 4)))

    rows = session.exec(
        select(UnifiedThread, Lead)
        .join(Lead, Lead.id == UnifiedThread.lead_id)
        .where(
            UnifiedThread.tenant_id == auth.tenant.id,
            Lead.tenant_id == auth.tenant.id,
            Lead.workspace_id == workspace_id,
        )
        .order_by(UnifiedThread.updated_at.desc())
    ).all()

    results: List[AICRMThreadRow] = []
    for thread, lead in rows:
        state = upsert_thread_state(session, auth.tenant.id, workspace_id, thread.id, lead.id)
        total_messages = int(
            session.exec(
                select(func.count(UnifiedMessage.id)).where(
                    UnifiedMessage.tenant_id == auth.tenant.id,
                    UnifiedMessage.thread_id == thread.id,
                )
            ).one()
        )
        last_msg = session.exec(
            select(UnifiedMessage)
            .where(
                UnifiedMessage.tenant_id == auth.tenant.id,
                UnifiedMessage.thread_id == thread.id,
            )
            .order_by(UnifiedMessage.created_at.desc())
            .limit(1)
        ).first()

        results.append(
            AICRMThreadRow(
                thread_id=thread.id,
                lead_id=lead.id,
                lead_name=lead.name,
                lead_external_id=lead.external_id,
                total_messages=total_messages,
                status=state.status.value,
                customer_reaction=state.customer_reaction,
                summary=state.summary,
                reject_count=int(state.reject_count or 0),
                followup_strategy=state.followup_strategy.value,
                aggressiveness=state.aggressiveness.value,
                next_followup_at=state.next_followup_at,
                last_scanned_at=state.last_scanned_at,
                last_scanned_message_count=int(state.last_scanned_message_count or 0),
                pending_scan=bool(total_messages - int(state.last_scanned_message_count or 0) >= threshold),
                last_message_preview=(last_msg.text_content[:140] if last_msg and last_msg.text_content else None),
                last_message_direction=(last_msg.direction if last_msg else None),
                last_message_at=(last_msg.created_at if last_msg else None),
                reason_trace=(state.reason_trace if isinstance(state.reason_trace, dict) else None),
            )
        )

    return results


@router.post("/{workspace_id}/ai-crm/scan", response_model=AICRMScanResponse)
async def scan_ai_crm_threads(
    workspace_id: int,
    payload: AICRMScanRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
    llm_router: LLMRouter = Depends(get_llm_router),
):
    validate_workspace(session, auth.tenant.id, workspace_id)
    return await scan_workspace_threads(
        session=session,
        router=llm_router,
        tenant_id=auth.tenant.id,
        workspace_id=workspace_id,
        force_all=bool(payload.force_all),
    )


@router.post("/{workspace_id}/ai-crm/trigger-due", response_model=AICRMTriggerResponse)
async def trigger_ai_crm_due_followups(
    workspace_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
    llm_router: LLMRouter = Depends(get_llm_router),
):
    validate_workspace(session, auth.tenant.id, workspace_id)
    return await trigger_due_followups(
        session=session,
        router=llm_router,
        tenant_id=auth.tenant.id,
        workspace_id=workspace_id,
    )
