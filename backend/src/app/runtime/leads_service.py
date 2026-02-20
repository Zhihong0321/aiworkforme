"""
Shared lead operations that should work with or without explicit workspace UX.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from src.adapters.db.calendar_models import CalendarEvent
from src.adapters.db.crm_models import ChatMessageNew, ConversationThread, Lead, LeadMemory, Workspace
from src.adapters.db.crm_models import PolicyDecision
from src.adapters.db.messaging_models import OutboundQueue, ThreadInsight, UnifiedMessage, UnifiedThread

DEFAULT_WORKSPACE_NAME = "Default"


def get_or_create_default_workspace(session: Session, tenant_id: int) -> Workspace:
    workspace = session.exec(
        select(Workspace).where(
            Workspace.tenant_id == tenant_id,
            Workspace.name == DEFAULT_WORKSPACE_NAME,
        )
    ).first()
    if workspace:
        return workspace

    workspace = Workspace(tenant_id=tenant_id, name=DEFAULT_WORKSPACE_NAME)
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace


def get_tenant_lead_or_404(session: Session, tenant_id: int, lead_id: int) -> Lead:
    lead = session.get(Lead, lead_id)
    if not lead or lead.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


def set_lead_mode_value(lead: Lead, mode_raw: str) -> Lead:
    mode = (mode_raw or "").strip().lower()
    tags = [str(t) for t in (lead.tags or []) if str(t) not in {"ON_HOLD", "WORKING"}]
    stage_value = lead.stage.value if hasattr(lead.stage, "value") else str(lead.stage)

    if mode == "on_hold":
        tags.append("ON_HOLD")
    elif mode == "working":
        tags.append("WORKING")
        if stage_value == "NEW":
            lead.stage = "CONTACTED"
        lead.last_followup_review_at = datetime.utcnow()
    else:
        raise HTTPException(status_code=400, detail="mode must be one of: on_hold, working")

    lead.tags = tags
    return lead


def delete_lead_and_children(session: Session, tenant_id: int, lead: Lead) -> None:
    # Unified messaging cleanup.
    unified_messages = session.exec(
        select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == tenant_id,
            UnifiedMessage.lead_id == lead.id,
        )
    ).all()
    message_ids = [m.id for m in unified_messages if m.id is not None]
    if message_ids:
        queue_rows = session.exec(
            select(OutboundQueue).where(
                OutboundQueue.tenant_id == tenant_id,
                OutboundQueue.message_id.in_(message_ids),
            )
        ).all()
        for row in queue_rows:
            session.delete(row)

    thread_rows = session.exec(
        select(UnifiedThread).where(
            UnifiedThread.tenant_id == tenant_id,
            UnifiedThread.lead_id == lead.id,
        )
    ).all()
    thread_ids = [t.id for t in thread_rows if t.id is not None]
    if thread_ids:
        insight_rows = session.exec(
            select(ThreadInsight).where(
                ThreadInsight.tenant_id == tenant_id,
                ThreadInsight.thread_id.in_(thread_ids),
            )
        ).all()
        for row in insight_rows:
            session.delete(row)

    for row in unified_messages:
        session.delete(row)
    for row in thread_rows:
        session.delete(row)

    # Legacy conversation cleanup.
    legacy_threads = session.exec(
        select(ConversationThread).where(
            ConversationThread.tenant_id == tenant_id,
            ConversationThread.lead_id == lead.id,
        )
    ).all()
    legacy_thread_ids = [t.id for t in legacy_threads if t.id is not None]
    if legacy_thread_ids:
        legacy_messages = session.exec(
            select(ChatMessageNew).where(
                ChatMessageNew.tenant_id == tenant_id,
                ChatMessageNew.thread_id.in_(legacy_thread_ids),
            )
        ).all()
        for row in legacy_messages:
            session.delete(row)
    for row in legacy_threads:
        session.delete(row)

    # Other lead-linked rows.
    policy_rows = session.exec(
        select(PolicyDecision).where(
            PolicyDecision.tenant_id == tenant_id,
            PolicyDecision.lead_id == lead.id,
        )
    ).all()
    for row in policy_rows:
        session.delete(row)

    memory_row = session.exec(
        select(LeadMemory).where(
            LeadMemory.tenant_id == tenant_id,
            LeadMemory.lead_id == lead.id,
        )
    ).first()
    if memory_row:
        session.delete(memory_row)

    calendar_rows = session.exec(
        select(CalendarEvent).where(
            CalendarEvent.tenant_id == tenant_id,
            CalendarEvent.lead_id == lead.id,
        )
    ).all()
    for row in calendar_rows:
        session.delete(row)

    session.delete(lead)
    session.commit()
