"""
MODULE: AI CRM Helpers
PURPOSE: Shared normalization and helper logic for AI CRM routes/runtime.
DOES: Validate controls, parse AI outputs, and manage state helper operations.
DOES NOT: Register routes or orchestrate full scan/trigger cycles.
INVARIANTS: Validation error semantics and strategy mapping remain stable.
SAFE CHANGE: Keep helper outputs backward-compatible for existing workflows.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlmodel import Session, select

from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.crm_models import (
    AICRMAggressiveness,
    AICRMFollowupStrategy,
    AICRMLeadStatus,
    AICRMThreadState,
    AICRMWorkspaceControl,
    Lead,
    Workspace,
)
from src.adapters.db.messaging_models import UnifiedThread

from .ai_crm_schemas import AICRMControlResponse


def validate_workspace(session: Session, tenant_id: int, workspace_id: int) -> Workspace:
    workspace = session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def normalize_aggressiveness(value: str) -> AICRMAggressiveness:
    raw = (value or "").strip().upper()
    if raw not in {e.value for e in AICRMAggressiveness}:
        raise HTTPException(
            status_code=400,
            detail="aggressiveness must be PASSIVE, BALANCED, or AGGRESSIVE",
        )
    return AICRMAggressiveness(raw)


def normalize_strategy(value: str) -> AICRMFollowupStrategy:
    raw = (value or "").strip().upper()
    if raw not in {e.value for e in AICRMFollowupStrategy}:
        raise HTTPException(
            status_code=400,
            detail="strategy must be STOP, PROMO, DISCOUNT, or OTHER",
        )
    return AICRMFollowupStrategy(raw)


def ensure_control(session: Session, tenant_id: int, workspace_id: int) -> AICRMWorkspaceControl:
    control = session.exec(
        select(AICRMWorkspaceControl).where(
            AICRMWorkspaceControl.tenant_id == tenant_id,
            AICRMWorkspaceControl.workspace_id == workspace_id,
        )
    ).first()
    if control:
        return control

    control = AICRMWorkspaceControl(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        enabled=True,
        scan_frequency_messages=4,
        aggressiveness=AICRMAggressiveness.BALANCED,
        not_interested_strategy=AICRMFollowupStrategy.PROMO,
        rejected_strategy=AICRMFollowupStrategy.DISCOUNT,
        double_reject_strategy=AICRMFollowupStrategy.STOP,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(control)
    session.commit()
    session.refresh(control)
    return control


def as_control_response(control: AICRMWorkspaceControl) -> AICRMControlResponse:
    return AICRMControlResponse(
        enabled=bool(control.enabled),
        scan_frequency_messages=int(control.scan_frequency_messages),
        aggressiveness=control.aggressiveness.value,
        not_interested_strategy=control.not_interested_strategy.value,
        rejected_strategy=control.rejected_strategy.value,
        double_reject_strategy=control.double_reject_strategy.value,
    )


def status_from_text(text: str, last_direction: str) -> Tuple[AICRMLeadStatus, str, str, Optional[int]]:
    raw = (text or "").strip()
    low = raw.lower()
    if not raw:
        return AICRMLeadStatus.NO_RESPONSE, "No clear reply.", "No customer response detected.", 48

    reject_tokens = ["not interested", "no thanks", "do not", "don't", "stop", "remove", "no need"]
    deny_tokens = ["reject", "decline", "cannot", "can't", "too expensive", "expensive"]
    consider_tokens = ["thinking", "consider", "later", "maybe", "let me check", "need time"]
    positive_tokens = ["yes", "interested", "sounds good", "okay", "ok", "let's", "book", "buy"]

    if any(token in low for token in reject_tokens):
        return AICRMLeadStatus.NOT_INTERESTED, "Not interested", "Lead asked to stop or showed no interest.", 96
    if any(token in low for token in deny_tokens):
        return AICRMLeadStatus.REJECTED, "Rejected", "Lead rejected the offer.", 120
    if any(token in low for token in positive_tokens):
        return AICRMLeadStatus.POSITIVE, "Positive", "Lead replied positively.", 12
    if any(token in low for token in consider_tokens):
        return AICRMLeadStatus.CONSIDERING, "Considering", "Lead is considering and asked for time.", 24

    if last_direction != "inbound":
        return AICRMLeadStatus.NO_RESPONSE, "No response", "No recent customer reply after outreach.", 48

    return AICRMLeadStatus.CONSIDERING, "Considering", "Neutral reply; likely still evaluating.", 24


def safe_status(raw_status: Any) -> AICRMLeadStatus:
    value = str(raw_status or "").strip().upper()
    mapping = {
        "NO_RESPONSE": AICRMLeadStatus.NO_RESPONSE,
        "CONSIDERING": AICRMLeadStatus.CONSIDERING,
        "POSITIVE": AICRMLeadStatus.POSITIVE,
        "NOT_INTERESTED": AICRMLeadStatus.NOT_INTERESTED,
        "REJECTED": AICRMLeadStatus.REJECTED,
        "DOUBLE_REJECT": AICRMLeadStatus.DOUBLE_REJECT,
        "DOUBLE-REJECT": AICRMLeadStatus.DOUBLE_REJECT,
    }
    return mapping.get(value, AICRMLeadStatus.NO_RESPONSE)


def strategy_for_status(control: AICRMWorkspaceControl, status: AICRMLeadStatus) -> AICRMFollowupStrategy:
    if status == AICRMLeadStatus.NOT_INTERESTED:
        return control.not_interested_strategy
    if status == AICRMLeadStatus.REJECTED:
        return control.rejected_strategy
    if status == AICRMLeadStatus.DOUBLE_REJECT:
        return control.double_reject_strategy
    return AICRMFollowupStrategy.PROMO


def base_hours_for_aggressiveness(aggressiveness: AICRMAggressiveness) -> int:
    return {
        AICRMAggressiveness.PASSIVE: 72,
        AICRMAggressiveness.BALANCED: 48,
        AICRMAggressiveness.AGGRESSIVE: 24,
    }.get(aggressiveness, 48)


def compute_next_followup_at(
    aggressiveness: AICRMAggressiveness,
    status: AICRMLeadStatus,
    strategy: AICRMFollowupStrategy,
    recommended_hours: Optional[int],
) -> Optional[datetime]:
    planned_hours = compute_planned_followup_hours(
        aggressiveness=aggressiveness,
        status=status,
        strategy=strategy,
        recommended_hours=recommended_hours,
    )
    if planned_hours is None:
        return None
    return datetime.utcnow() + timedelta(hours=planned_hours)


def compute_planned_followup_hours(
    aggressiveness: AICRMAggressiveness,
    status: AICRMLeadStatus,
    strategy: AICRMFollowupStrategy,
    recommended_hours: Optional[int],
) -> Optional[int]:
    if strategy == AICRMFollowupStrategy.STOP:
        return None

    base = base_hours_for_aggressiveness(aggressiveness)
    multiplier = {
        AICRMLeadStatus.POSITIVE: 0.5,
        AICRMLeadStatus.CONSIDERING: 0.75,
        AICRMLeadStatus.NO_RESPONSE: 1.0,
        AICRMLeadStatus.NOT_INTERESTED: 1.5,
        AICRMLeadStatus.REJECTED: 2.0,
        AICRMLeadStatus.DOUBLE_REJECT: 2.5,
    }.get(status, 1.0)
    planned_hours = int(max(6, min(336, round(base * multiplier))))

    if recommended_hours and recommended_hours > 0:
        rec = int(max(6, min(336, recommended_hours)))
        planned_hours = int(max(6, min(336, round((planned_hours + rec) / 2))))

    return planned_hours


def parse_json_from_llm(content: str) -> Dict[str, Any]:
    text = (content or "").strip()
    if not text:
        return {}

    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except Exception:
        return {}


async def analyze_thread_with_ai(
    router,
    control: AICRMWorkspaceControl,
    messages,
) -> Dict[str, Any]:
    history_lines: List[str] = []
    for item in messages[-12:]:
        role = "customer" if item.direction == "inbound" else "agent"
        content = (item.text_content or "").strip()
        if not content:
            continue
        history_lines.append(f"[{role}] {content}")

    history_blob = "\n".join(history_lines)
    system_prompt = (
        "Classify CRM thread state and output strict JSON only. "
        "Valid statuses: NO_RESPONSE, CONSIDERING, POSITIVE, NOT_INTERESTED, REJECTED. "
        "Do not output markdown."
    )
    user_prompt = (
        "Analyze this conversation and return JSON with keys: "
        "status, customer_reaction, summary, recommended_followup_hours.\n\n"
        f"Aggressiveness: {control.aggressiveness.value}.\n"
        f"Conversation:\n{history_blob}"
    )

    from src.infra.llm.schemas import LLMTask

    response = await router.execute(
        task=LLMTask.AI_CRM,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=240,
    )
    parsed = parse_json_from_llm(response.content or "")

    if parsed:
        parsed["_analysis_source"] = "ai_json"
        return parsed

    fallback_text = ""
    last_direction = ""
    for item in reversed(messages):
        if item.text_content:
            fallback_text = item.text_content
            last_direction = item.direction
            break

    status, reaction, summary, recommended = status_from_text(fallback_text, last_direction)
    return {
        "status": status.value,
        "customer_reaction": reaction,
        "summary": summary,
        "recommended_followup_hours": recommended,
        "_analysis_source": "heuristic_fallback",
    }


async def generate_followup_text(
    router,
    lead_name: Optional[str],
    state: AICRMThreadState,
    strategy: AICRMFollowupStrategy,
    messages,
) -> str:
    history_lines: List[str] = []
    for item in messages[-10:]:
        role = "customer" if item.direction == "inbound" else "agent"
        content = (item.text_content or "").strip()
        if content:
            history_lines.append(f"[{role}] {content}")

    guidance = {
        AICRMFollowupStrategy.PROMO: "Offer a soft promo without pressure.",
        AICRMFollowupStrategy.DISCOUNT: "Offer a clear discount and urgency, still respectful.",
        AICRMFollowupStrategy.OTHER: "Use a value-first re-engagement message.",
        AICRMFollowupStrategy.STOP: "Do not send any follow-up.",
    }[strategy]

    if strategy == AICRMFollowupStrategy.STOP:
        return ""

    from src.infra.llm.schemas import LLMTask

    response = await router.execute(
        task=LLMTask.AI_CRM,
        messages=[
            {
                "role": "system",
                "content": "Write one short WhatsApp follow-up message. Keep it human, concise, and polite.",
            },
            {
                "role": "user",
                "content": (
                    f"Lead name: {lead_name or 'there'}.\n"
                    f"Status: {state.status.value}.\n"
                    f"Aggressiveness: {state.aggressiveness.value}.\n"
                    f"Strategy: {strategy.value}. {guidance}\n"
                    f"Recent conversation:\n" + "\n".join(history_lines)
                ),
            },
        ],
        temperature=0.4,
        max_tokens=140,
    )
    text = (response.content or "").strip()
    if text:
        return text

    name = lead_name or "there"
    if strategy == AICRMFollowupStrategy.DISCOUNT:
        return f"Hi {name}, quick follow-up: we can offer a special discount if you want to continue. Want the details?"
    if strategy == AICRMFollowupStrategy.PROMO:
        return f"Hi {name}, just checking in. We currently have a promo that might fit what you were looking for."
    return f"Hi {name}, following up in case timing is better now. Happy to help if you still want this."


def upsert_thread_state(
    session: Session,
    tenant_id: int,
    workspace_id: int,
    thread_id: int,
    lead_id: int,
) -> AICRMThreadState:
    state = session.exec(
        select(AICRMThreadState).where(
            AICRMThreadState.tenant_id == tenant_id,
            AICRMThreadState.workspace_id == workspace_id,
            AICRMThreadState.thread_id == thread_id,
        )
    ).first()
    if state:
        return state

    state = AICRMThreadState(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        thread_id=thread_id,
        lead_id=lead_id,
        status=AICRMLeadStatus.NO_RESPONSE,
        followup_strategy=AICRMFollowupStrategy.PROMO,
        aggressiveness=AICRMAggressiveness.BALANCED,
        reject_count=0,
        last_scanned_message_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


def resolve_channel_session_id(session: Session, tenant_id: int, channel: str) -> Optional[int]:
    if channel != "whatsapp":
        return None

    active = session.exec(
        select(ChannelSession)
        .where(
            ChannelSession.tenant_id == tenant_id,
            ChannelSession.channel_type == ChannelType.WHATSAPP,
            ChannelSession.status == SessionStatus.ACTIVE,
        )
        .order_by(ChannelSession.updated_at.desc())
        .limit(1)
    ).first()
    return int(active.id) if active and active.id else None
