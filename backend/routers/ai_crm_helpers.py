"""
MODULE: AI CRM Helpers
PURPOSE: Shared normalization and helper logic for AI CRM routes/runtime.
DOES: Validate controls, parse AI outputs, and manage state helper operations.
DOES NOT: Register routes or orchestrate full scan/trigger cycles.
INVARIANTS: Validation error semantics and strategy mapping remain stable.
SAFE CHANGE: Keep helper outputs backward-compatible for existing workflows.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlmodel import Session, select, text

from src.adapters.db.agent_models import Agent
from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.crm_models import (
    AgentCRMProfile,
    AICRMAggressiveness,
    AICRMFollowupStrategy,
    AICRMFollowupMessageType,
    AICRMLeadStatus,
    AICRMThreadState,
    Lead,
    Workspace,
)
from src.adapters.db.messaging_models import UnifiedMessage, UnifiedThread
from src.app.conversation_skills import (
    ConversationTaskKind,
    compose_conversation_prompt,
    get_default_conversation_skill_registry,
)
from src.app.runtime.leads_service import get_or_create_default_workspace

from .ai_crm_schemas import AICRMControlResponse
from .messaging_helpers_validation import resolve_agent_for_lead, sync_whatsapp_thread_assignment


logger = logging.getLogger(__name__)


def validate_agent(session: Session, tenant_id: int, agent_id: int) -> Agent:
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


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


def ensure_control(session: Session, tenant_id: int, agent_id: int) -> AgentCRMProfile:
    control = session.exec(
        select(AgentCRMProfile).where(
            AgentCRMProfile.tenant_id == tenant_id,
            AgentCRMProfile.agent_id == agent_id,
        )
    ).first()
    if control:
        return control

    control = AgentCRMProfile(
        tenant_id=tenant_id,
        agent_id=agent_id,
        enabled=True,
        scan_frequency_messages=4,
        aggressiveness=AICRMAggressiveness.BALANCED,
        review_after_hours=24,
        allow_voice_notes=False,
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


def as_control_response(control: AgentCRMProfile) -> AICRMControlResponse:
    return AICRMControlResponse(
        enabled=bool(control.enabled),
        scan_frequency_messages=int(control.scan_frequency_messages),
        aggressiveness=control.aggressiveness.value,
        review_after_hours=int(control.review_after_hours or 24),
        allow_voice_notes=bool(control.allow_voice_notes),
        not_interested_strategy=control.not_interested_strategy.value,
        rejected_strategy=control.rejected_strategy.value,
        double_reject_strategy=control.double_reject_strategy.value,
    )


def synchronize_active_thread_assignments(session: Session, tenant_id: int) -> int:
    rows = session.exec(
        select(UnifiedThread, Lead)
        .join(Lead, Lead.id == UnifiedThread.lead_id)
        .where(
            UnifiedThread.tenant_id == tenant_id,
            UnifiedThread.status == "active",
            Lead.tenant_id == tenant_id,
            UnifiedThread.channel == "whatsapp",
        )
    ).all()

    changed = 0
    for thread, lead in rows:
        latest_channel_session_id = session.exec(
            select(UnifiedMessage.channel_session_id)
            .where(
                UnifiedMessage.tenant_id == tenant_id,
                UnifiedMessage.thread_id == thread.id,
                UnifiedMessage.channel_session_id.is_not(None),
            )
            .order_by(UnifiedMessage.created_at.desc(), UnifiedMessage.id.desc())
            .limit(1)
        ).first()
        if latest_channel_session_id is not None:
            if sync_whatsapp_thread_assignment(
                session=session,
                tenant_id=tenant_id,
                lead=lead,
                thread=thread,
                channel_session_id=int(latest_channel_session_id),
            ):
                changed += 1
                continue

        if thread.agent_id is None:
            try:
                repaired_agent_id = resolve_agent_for_lead(session, tenant_id, int(lead.id))
            except HTTPException:
                repaired_agent_id = None
            if repaired_agent_id is not None:
                thread.agent_id = repaired_agent_id
                thread.updated_at = datetime.utcnow()
                session.add(thread)
                changed += 1
                if lead.agent_id != repaired_agent_id:
                    lead.agent_id = repaired_agent_id
                    session.add(lead)
                continue

        if thread.agent_id is not None and lead.agent_id != thread.agent_id:
            lead.agent_id = thread.agent_id
            session.add(lead)
            changed += 1

    if changed:
        session.commit()

    return changed


def status_from_text(text: str, last_direction: str) -> Tuple[AICRMLeadStatus, str, str, Optional[int]]:
    raw = (text or "").strip()
    low = raw.lower()
    if not raw:
        return AICRMLeadStatus.NO_RESPONSE, "No clear reply.", "No customer response detected.", 0

    reject_tokens = ["not interested", "no thanks", "do not", "don't", "stop", "remove", "no need"]
    deny_tokens = ["reject", "decline", "cannot", "can't", "too expensive", "expensive"]
    consider_tokens = ["thinking", "consider", "later", "maybe", "let me check", "need time"]
    positive_tokens = ["yes", "interested", "sounds good", "okay", "ok", "let's", "book", "buy"]

    if any(token in low for token in reject_tokens):
        return AICRMLeadStatus.NOT_INTERESTED, "Not interested", "Lead asked to stop or showed no interest.", None
    if any(token in low for token in deny_tokens):
        return AICRMLeadStatus.REJECTED, "Rejected", "Lead rejected the offer.", None
    if any(token in low for token in positive_tokens):
        return AICRMLeadStatus.POSITIVE, "Positive", "Lead replied positively.", 12
    if any(token in low for token in consider_tokens):
        return AICRMLeadStatus.CONSIDERING, "Considering", "Lead is considering and asked for time.", 24

    if last_direction != "inbound":
        return AICRMLeadStatus.NO_RESPONSE, "No response", "No recent customer reply after outreach.", 0

    return AICRMLeadStatus.CONSIDERING, "Considering", "Neutral reply; likely still evaluating.", 24


def normalize_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    raw = str(value or "").strip().lower()
    if raw in {"true", "1", "yes", "y"}:
        return True
    if raw in {"false", "0", "no", "n"}:
        return False
    return default


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


def strategy_for_status(control: AgentCRMProfile, status: AICRMLeadStatus) -> AICRMFollowupStrategy:
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


def clamp_wait_hours(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    return int(max(0, min(24 * 30, int(value))))


def safe_message_type(raw_value: Any, allow_voice_notes: bool) -> AICRMFollowupMessageType:
    normalized = str(raw_value or "").strip().lower()
    if normalized == AICRMFollowupMessageType.AUDIO.value and allow_voice_notes:
        return AICRMFollowupMessageType.AUDIO
    return AICRMFollowupMessageType.TEXT


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

    if recommended_hours is not None:
        return clamp_wait_hours(recommended_hours)

    base = base_hours_for_aggressiveness(aggressiveness)
    multiplier = {
        AICRMLeadStatus.POSITIVE: 0.5,
        AICRMLeadStatus.CONSIDERING: 0.75,
        AICRMLeadStatus.NO_RESPONSE: 1.0,
        AICRMLeadStatus.NOT_INTERESTED: 1.5,
        AICRMLeadStatus.REJECTED: 2.0,
        AICRMLeadStatus.DOUBLE_REJECT: 2.5,
    }.get(status, 1.0)
    return int(max(6, min(336, round(base * multiplier))))


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
    control: AgentCRMProfile,
    messages,
    silence_hours: float,
    review_after_hours: int,
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
        "You are a CRM review engine for dormant sales conversations. Output strict JSON only. "
        "Valid statuses: NO_RESPONSE, CONSIDERING, POSITIVE, NOT_INTERESTED, REJECTED, DOUBLE_REJECT. "
        "Valid recommended_message_type values: text, audio. "
        "Do not output markdown."
    )
    user_prompt = (
        "Analyze this conversation and return JSON with keys: "
        "status, customer_reaction, summary, should_follow_up, recommended_wait_hours, recommended_message_type.\n\n"
        f"Aggressiveness: {control.aggressiveness.value}.\n"
        f"Voice notes allowed: {bool(control.allow_voice_notes)}.\n"
        f"The thread becomes reviewable after {review_after_hours} hours with no customer reply.\n"
        f"It has currently been silent for {round(float(silence_hours), 1)} hours since the last outbound message.\n"
        "Interpret recommended_wait_hours as hours from now until the next follow-up. "
        "Return 0 if a follow-up should be sent now. Return null if no follow-up should be scheduled.\n"
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
        "should_follow_up": status not in {AICRMLeadStatus.NOT_INTERESTED, AICRMLeadStatus.REJECTED},
        "recommended_wait_hours": recommended,
        "recommended_message_type": "text",
        "_analysis_source": "heuristic_fallback",
    }


async def generate_followup_text(
    router,
    lead_name: Optional[str],
    state: AICRMThreadState,
    strategy: AICRMFollowupStrategy,
    message_type: AICRMFollowupMessageType,
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
    composed = compose_conversation_prompt(
        registry=get_default_conversation_skill_registry(),
        base_prompt=(
            "Write one short WhatsApp voice-note script. Keep it spoken, human, concise, and polite."
            if message_type == AICRMFollowupMessageType.AUDIO
            else "Write one short WhatsApp follow-up message. Keep it human, concise, and polite."
        ),
        task_kind=(
            ConversationTaskKind.VOICE_NOTE_GENERATION
            if message_type == AICRMFollowupMessageType.AUDIO
            else ConversationTaskKind.FOLLOWUP_GENERATION
        ),
        channel="whatsapp",
        agent_id=state.agent_id,
        tenant_id=state.tenant_id,
    )

    response = await router.execute(
        task=LLMTask.AI_CRM,
        messages=[
            {
                "role": "system",
                "content": composed.system_prompt,
            },
            {
                "role": "user",
                "content": (
                    f"Lead name: {lead_name or 'there'}.\n"
                    f"Status: {state.status.value}.\n"
                    f"Aggressiveness: {state.aggressiveness.value}.\n"
                    f"Format: {message_type.value}.\n"
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
    agent_id: int,
    thread_id: int,
    lead_id: int,
    workspace_id: Optional[int] = None,
) -> AICRMThreadState:
    workspace_id = resolve_thread_state_workspace_id(
        session=session,
        tenant_id=tenant_id,
        agent_id=agent_id,
        lead_id=lead_id,
        workspace_id=workspace_id,
    )
    state = session.exec(
        select(AICRMThreadState).where(
            AICRMThreadState.tenant_id == tenant_id,
            AICRMThreadState.thread_id == thread_id,
        )
    ).first()
    if state:
        changed = False
        if int(state.agent_id or 0) != int(agent_id):
            state.agent_id = agent_id
            changed = True
        if int(state.lead_id or 0) != int(lead_id):
            state.lead_id = lead_id
            changed = True
        if state.workspace_id != workspace_id:
            state.workspace_id = workspace_id
            changed = True
        if changed:
            state.updated_at = datetime.utcnow()
            session.add(state)
            session.commit()
            session.refresh(state)
        return state

    state = AICRMThreadState(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        agent_id=agent_id,
        thread_id=thread_id,
        lead_id=lead_id,
        status=AICRMLeadStatus.NO_RESPONSE,
        followup_strategy=AICRMFollowupStrategy.PROMO,
        followup_message_type=AICRMFollowupMessageType.TEXT,
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


def resolve_thread_state_workspace_id(
    session: Session,
    tenant_id: int,
    agent_id: int,
    lead_id: int,
    workspace_id: Optional[int],
) -> int:
    if workspace_id is not None:
        return int(workspace_id)

    lead = session.get(Lead, lead_id)
    if not lead or int(lead.tenant_id or 0) != int(tenant_id):
        raise HTTPException(status_code=404, detail="Lead not found for AI CRM thread state")

    if lead.workspace_id is not None:
        return int(lead.workspace_id)

    workspace = session.exec(
        select(Workspace)
        .where(
            Workspace.tenant_id == tenant_id,
            Workspace.agent_id == agent_id,
        )
        .order_by(Workspace.id.asc())
    ).first()
    if workspace is None:
        workspace = get_or_create_default_workspace(session, tenant_id)

    lead.workspace_id = int(workspace.id)
    session.add(lead)
    session.commit()
    session.refresh(lead)
    logger.info(
        "AI CRM assigned workspace %s to lead %s before creating thread state",
        workspace.id,
        lead.id,
    )
    return int(workspace.id)


def resolve_channel_session_id(
    session: Session,
    tenant_id: int,
    channel: str,
    agent_id: Optional[int] = None,
    fallback_channel_session_id: Optional[int] = None,
) -> Optional[int]:
    if channel != "whatsapp":
        return None

    if not agent_id:
        return None

    agent = session.get(Agent, agent_id)
    preferred_session_id = getattr(agent, "preferred_channel_session_id", None) if agent else None
    if not preferred_session_id:
        return None

    preferred_session = session.get(ChannelSession, preferred_session_id)
    if (
        preferred_session
        and preferred_session.tenant_id == tenant_id
        and preferred_session.channel_type == ChannelType.WHATSAPP
        and preferred_session.status == SessionStatus.ACTIVE
    ):
        return int(preferred_session.id)
    return None


def clear_thread_followup_state(
    session: Session,
    tenant_id: int,
    thread_id: Optional[int],
    reason: str,
) -> None:
    if thread_id is None:
        return

    try:
        state = session.exec(
            select(AICRMThreadState).where(
                AICRMThreadState.tenant_id == tenant_id,
                AICRMThreadState.thread_id == thread_id,
            )
        ).first()
        if not state:
            return

        trace = dict(state.reason_trace or {})
        trace["last_reset_reason"] = reason
        trace["last_reset_at"] = datetime.utcnow().isoformat()
        state.next_followup_at = None
        state.followup_last_generated_at = None
        state.updated_at = datetime.utcnow()
        state.reason_trace = trace
        session.add(state)
        session.commit()
        return
    except Exception as exc:
        session.rollback()
        logger.warning(
            "Falling back to raw AI CRM state reset for tenant_id=%s thread_id=%s: %s",
            tenant_id,
            thread_id,
            exc,
        )

    session.connection().execute(
        text(
            """
            UPDATE et_ai_crm_thread_states
            SET next_followup_at = NULL,
                followup_last_generated_at = NULL,
                updated_at = :updated_at
            WHERE tenant_id = :tenant_id
              AND thread_id = :thread_id
            """
        ),
        {
            "tenant_id": tenant_id,
            "thread_id": thread_id,
            "updated_at": datetime.utcnow(),
        },
    )
    session.commit()
