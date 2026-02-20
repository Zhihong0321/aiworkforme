"""
MODULE: AI CRM Runtime
PURPOSE: Core scan/trigger orchestration and background cycle execution.
DOES: Execute AI CRM workflows using helper modules and persistence models.
DOES NOT: Declare HTTP route handlers.
INVARIANTS: Scan/trigger side effects and counters remain compatible.
SAFE CHANGE: Preserve queueing and state-update semantics.
"""

from datetime import datetime, timedelta
from typing import Dict, List
from uuid import uuid4
import logging

from sqlmodel import Session, func, select

from src.adapters.db.crm_models import (
    AICRMFollowupStrategy,
    AICRMLeadStatus,
    AICRMThreadState,
    AICRMWorkspaceControl,
    Lead,
)
from src.adapters.db.messaging_models import OutboundQueue, UnifiedMessage, UnifiedThread
from src.infra.llm.router import LLMRouter

from .ai_crm_helpers import (
    analyze_thread_with_ai,
    base_hours_for_aggressiveness,
    compute_next_followup_at,
    compute_planned_followup_hours,
    ensure_control,
    generate_followup_text,
    resolve_channel_session_id,
    safe_status,
    strategy_for_status,
    upsert_thread_state,
)
from .ai_crm_schemas import AICRMScanResponse, AICRMTriggerResponse

logger = logging.getLogger(__name__)


def fast_forward_followups(
    session: Session,
    tenant_id: int,
    workspace_id: int,
    seconds: int = 5,
    include_overdue: bool = True,
):
    seconds = max(1, min(120, int(seconds or 5)))
    now = datetime.utcnow()
    target_followup_at = now + timedelta(seconds=seconds)

    filters = [
        AICRMThreadState.tenant_id == tenant_id,
        AICRMThreadState.workspace_id == workspace_id,
        AICRMThreadState.next_followup_at.is_not(None),
        AICRMThreadState.followup_strategy != AICRMFollowupStrategy.STOP,
    ]
    if not include_overdue:
        filters.append(AICRMThreadState.next_followup_at > now)

    states = session.exec(select(AICRMThreadState).where(*filters)).all()
    updated_states = 0

    for state in states:
        state.next_followup_at = target_followup_at
        trace = dict(state.reason_trace or {})
        trace["test_fast_forward_applied_at"] = now.isoformat()
        trace["test_fast_forward_seconds"] = seconds
        trace["test_fast_forward_target_followup_at"] = target_followup_at.isoformat()
        state.reason_trace = trace
        state.updated_at = now
        session.add(state)

        lead = session.get(Lead, state.lead_id)
        if lead:
            lead.next_followup_at = target_followup_at
            session.add(lead)

        updated_states += 1

    session.commit()
    return target_followup_at, updated_states


async def scan_workspace_threads(
    session: Session,
    router: LLMRouter,
    tenant_id: int,
    workspace_id: int,
    force_all: bool,
) -> AICRMScanResponse:
    control = ensure_control(session, tenant_id, workspace_id)
    rows = session.exec(
        select(UnifiedThread, Lead)
        .join(Lead, Lead.id == UnifiedThread.lead_id)
        .where(
            UnifiedThread.tenant_id == tenant_id,
            Lead.tenant_id == tenant_id,
            Lead.workspace_id == workspace_id,
        )
        .order_by(UnifiedThread.updated_at.desc())
    ).all()

    scanned_threads = 0
    skipped_threads = 0
    next_followups_set = 0
    errors: List[str] = []

    for thread, lead in rows:
        try:
            state = upsert_thread_state(session, tenant_id, workspace_id, thread.id, lead.id)
            total_messages = int(
                session.exec(
                    select(func.count(UnifiedMessage.id)).where(
                        UnifiedMessage.tenant_id == tenant_id,
                        UnifiedMessage.thread_id == thread.id,
                    )
                ).one()
            )

            threshold = max(3, min(10, int(control.scan_frequency_messages or 4)))
            should_scan = force_all or (
                total_messages >= threshold
                and (total_messages - int(state.last_scanned_message_count or 0) >= threshold)
            )

            if not should_scan:
                skipped_threads += 1
                continue

            messages = session.exec(
                select(UnifiedMessage)
                .where(
                    UnifiedMessage.tenant_id == tenant_id,
                    UnifiedMessage.thread_id == thread.id,
                )
                .order_by(UnifiedMessage.created_at.asc())
            ).all()
            if not messages:
                skipped_threads += 1
                continue

            parsed = await analyze_thread_with_ai(router, control, messages)
            detected_status = safe_status(parsed.get("status"))
            raw_detected_status = str(parsed.get("status") or "").strip().upper() or "NO_RESPONSE"

            reject_count = int(state.reject_count or 0)
            if detected_status in {AICRMLeadStatus.NOT_INTERESTED, AICRMLeadStatus.REJECTED}:
                reject_count = reject_count + 1
                if reject_count >= 2:
                    detected_status = AICRMLeadStatus.DOUBLE_REJECT
            elif detected_status == AICRMLeadStatus.DOUBLE_REJECT:
                reject_count = max(2, reject_count + 1)
            else:
                reject_count = 0

            strategy = strategy_for_status(control, detected_status)
            recommended_hours = parsed.get("recommended_followup_hours")
            try:
                recommended_hours = int(recommended_hours) if recommended_hours is not None else None
            except Exception:
                recommended_hours = None

            planned_followup_hours = compute_planned_followup_hours(
                aggressiveness=control.aggressiveness,
                status=detected_status,
                strategy=strategy,
                recommended_hours=recommended_hours,
            )
            next_followup_at = compute_next_followup_at(
                aggressiveness=control.aggressiveness,
                status=detected_status,
                strategy=strategy,
                recommended_hours=recommended_hours,
            )
            reason_trace = {
                "status_source": str(parsed.get("_analysis_source") or "heuristic_fallback"),
                "status_raw": raw_detected_status,
                "status_final": detected_status.value,
                "scan_frequency_messages": threshold,
                "message_count": total_messages,
                "messages_since_last_scan": max(0, total_messages - int(state.last_scanned_message_count or 0)),
                "aggressiveness": control.aggressiveness.value,
                "followup_strategy": strategy.value,
                "recommended_followup_hours": recommended_hours,
                "planned_followup_hours": planned_followup_hours,
                "next_followup_at": next_followup_at.isoformat() if next_followup_at else None,
                "reject_count": reject_count,
                "customer_reaction": str(parsed.get("customer_reaction") or "").strip()[:128] or None,
                "summary": str(parsed.get("summary") or "").strip()[:500] or None,
                "last_message_direction": messages[-1].direction if messages else None,
                "last_message_preview": ((messages[-1].text_content or "").strip()[:160] if messages else None),
                "scanned_at": datetime.utcnow().isoformat(),
            }

            state.status = detected_status
            state.summary = str(parsed.get("summary") or "").strip()[:500] or None
            state.customer_reaction = str(parsed.get("customer_reaction") or "").strip()[:128] or None
            state.followup_strategy = strategy
            state.aggressiveness = control.aggressiveness
            state.reject_count = reject_count
            state.reason_trace = reason_trace
            state.last_scanned_message_count = total_messages
            state.last_scanned_at = datetime.utcnow()
            state.next_followup_at = next_followup_at
            state.updated_at = datetime.utcnow()
            session.add(state)

            lead.next_followup_at = next_followup_at
            session.add(lead)

            session.commit()

            if next_followup_at is not None:
                next_followups_set += 1
            scanned_threads += 1
        except Exception as exc:
            session.rollback()
            logger.exception("AI CRM scan failed for thread %s", thread.id)
            errors.append(f"Thread {thread.id}: {str(exc)}")

    return AICRMScanResponse(
        workspace_id=workspace_id,
        scanned_threads=scanned_threads,
        skipped_threads=skipped_threads,
        next_followups_set=next_followups_set,
        errors=errors,
    )


async def trigger_due_followups(
    session: Session,
    router: LLMRouter,
    tenant_id: int,
    workspace_id: int,
) -> AICRMTriggerResponse:
    control = ensure_control(session, tenant_id, workspace_id)
    if not control.enabled:
        return AICRMTriggerResponse(workspace_id=workspace_id, triggered=0, skipped=0, errors=[])

    now = datetime.utcnow()
    due_states = session.exec(
        select(AICRMThreadState)
        .where(
            AICRMThreadState.tenant_id == tenant_id,
            AICRMThreadState.workspace_id == workspace_id,
            AICRMThreadState.next_followup_at.is_not(None),
            AICRMThreadState.next_followup_at <= now,
        )
        .order_by(AICRMThreadState.next_followup_at.asc())
    ).all()

    triggered = 0
    skipped = 0
    errors: List[str] = []

    for state in due_states:
        try:
            if state.followup_strategy == AICRMFollowupStrategy.STOP:
                state.next_followup_at = None
                trace = dict(state.reason_trace or {})
                trace["last_trigger_decision"] = "skipped_stop_strategy"
                trace["last_trigger_checked_at"] = datetime.utcnow().isoformat()
                state.reason_trace = trace
                state.updated_at = datetime.utcnow()
                session.add(state)
                session.commit()
                skipped += 1
                continue

            lead = session.get(Lead, state.lead_id)
            thread = session.get(UnifiedThread, state.thread_id)
            if not lead or not thread:
                skipped += 1
                continue

            queued_exists = session.exec(
                select(OutboundQueue)
                .join(UnifiedMessage, UnifiedMessage.id == OutboundQueue.message_id)
                .where(
                    OutboundQueue.tenant_id == tenant_id,
                    OutboundQueue.status.in_(["queued", "dispatching", "accepted"]),
                    UnifiedMessage.lead_id == lead.id,
                    UnifiedMessage.created_at >= now - timedelta(hours=6),
                )
                .limit(1)
            ).first()
            if queued_exists:
                skipped += 1
                continue

            messages = session.exec(
                select(UnifiedMessage)
                .where(
                    UnifiedMessage.tenant_id == tenant_id,
                    UnifiedMessage.thread_id == thread.id,
                )
                .order_by(UnifiedMessage.created_at.asc())
            ).all()

            text = await generate_followup_text(
                router=router,
                lead_name=lead.name,
                state=state,
                strategy=state.followup_strategy,
                messages=messages,
            )
            if not text:
                skipped += 1
                continue

            channel_session_id = resolve_channel_session_id(session, tenant_id, thread.channel)
            if thread.channel == "whatsapp" and not channel_session_id:
                errors.append(f"State {state.id}: no active WhatsApp session available.")
                skipped += 1
                continue

            outbound = UnifiedMessage(
                tenant_id=tenant_id,
                lead_id=lead.id,
                thread_id=thread.id,
                channel_session_id=channel_session_id,
                channel=thread.channel,
                external_message_id=f"out_{uuid4().hex}",
                direction="outbound",
                message_type="text",
                text_content=text,
                raw_payload={
                    "source": "ai_crm_followup",
                    "ai_crm_state_id": state.id,
                    "status": state.status.value,
                    "strategy": state.followup_strategy.value,
                },
                delivery_status="queued",
                created_at=now,
                updated_at=now,
            )
            session.add(outbound)
            session.commit()
            session.refresh(outbound)

            queue = OutboundQueue(
                tenant_id=tenant_id,
                message_id=outbound.id,
                channel=thread.channel,
                channel_session_id=outbound.channel_session_id,
                status="queued",
                retry_count=0,
                next_attempt_at=now,
                created_at=now,
                updated_at=now,
            )
            session.add(queue)

            state.followup_last_generated_at = now
            trace = dict(state.reason_trace or {})
            trace["last_trigger_decision"] = "followup_enqueued"
            trace["last_triggered_at"] = now.isoformat()
            trace["last_trigger_message_preview"] = text[:160]
            state.reason_trace = trace
            if state.status in {
                AICRMLeadStatus.NOT_INTERESTED,
                AICRMLeadStatus.REJECTED,
                AICRMLeadStatus.DOUBLE_REJECT,
            }:
                state.next_followup_at = None
            else:
                state.next_followup_at = now + timedelta(hours=base_hours_for_aggressiveness(state.aggressiveness))
            state.updated_at = now
            session.add(state)

            lead.last_followup_at = now
            lead.next_followup_at = state.next_followup_at
            session.add(lead)

            session.commit()
            triggered += 1
        except Exception as exc:
            session.rollback()
            logger.exception("AI CRM due follow-up trigger failed for state %s", state.id)
            errors.append(f"State {state.id}: {str(exc)}")

    return AICRMTriggerResponse(
        workspace_id=workspace_id,
        triggered=triggered,
        skipped=skipped,
        errors=errors,
    )


async def run_ai_crm_background_cycle(session: Session, router: LLMRouter) -> Dict[str, int]:
    tenant_workspace_rows = session.exec(
        select(AICRMWorkspaceControl.tenant_id, AICRMWorkspaceControl.workspace_id)
        .where(AICRMWorkspaceControl.enabled == True)  # noqa: E712
    ).all()

    total_scanned = 0
    total_triggered = 0
    for tenant_id, workspace_id in tenant_workspace_rows:
        scan_result = await scan_workspace_threads(
            session=session,
            router=router,
            tenant_id=int(tenant_id),
            workspace_id=int(workspace_id),
            force_all=False,
        )
        trigger_result = await trigger_due_followups(
            session=session,
            router=router,
            tenant_id=int(tenant_id),
            workspace_id=int(workspace_id),
        )
        total_scanned += int(scan_result.scanned_threads)
        total_triggered += int(trigger_result.triggered)

    return {"scanned": total_scanned, "triggered": total_triggered}
