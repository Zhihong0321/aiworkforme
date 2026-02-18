from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from sqlmodel import SQLModel
from src.infra.database import get_session
from src.adapters.db.crm_models import Workspace, Lead, StrategyVersion, StrategyStatus
from src.adapters.db.agent_models import Agent
from src.adapters.api.dependencies import require_tenant_access, AuthContext
from src.adapters.db.messaging_models import UnifiedMessage, UnifiedThread, OutboundQueue, ThreadInsight
from src.adapters.db.crm_models import ConversationThread, ChatMessageNew, PolicyDecision, LeadMemory
from src.adapters.db.calendar_models import CalendarEvent

router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspace Management"])


class LeadModeRequest(SQLModel):
    mode: str  # on_hold | working


def _stage_value(stage) -> str:
    return stage.value if hasattr(stage, "value") else str(stage)

@router.get("/", response_model=List[Workspace])
def list_workspaces(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    return session.exec(select(Workspace).where(Workspace.tenant_id == auth.tenant.id)).all()

@router.post("/", response_model=Workspace)
def create_workspace(
    workspace: Workspace, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    workspace.tenant_id = auth.tenant.id
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace

@router.put("/{workspace_id}", response_model=Workspace)
def update_workspace(
    workspace_id: int, 
    agent_id: Optional[int] = None, 
    name: Optional[str] = None, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if agent_id is not None:
        # Verify agent exists
        agent = session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        ws.agent_id = agent_id
    
    if name:
        ws.name = name
    
    session.add(ws)
    session.commit()
    session.refresh(ws)
    return ws

@router.get("/{workspace_id}/leads", response_model=List[Lead])
def get_workspace_leads(
    workspace_id: int, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return session.exec(select(Lead).where(Lead.workspace_id == workspace_id)).all()

@router.get("/{workspace_id}/strategy", response_model=Optional[StrategyVersion])
def get_workspace_strategy(
    workspace_id: int, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return session.exec(
        select(StrategyVersion)
        .where(StrategyVersion.workspace_id == workspace_id)
        .where(StrategyVersion.status == StrategyStatus.ACTIVE)
    ).first()

@router.post("/{workspace_id}/strategy", response_model=StrategyVersion)
def update_workspace_strategy(
    workspace_id: int, 
    payload: StrategyVersion, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    # Deactivate old ones
    old_strategies = session.exec(
        select(StrategyVersion)
        .where(StrategyVersion.workspace_id == workspace_id)
    ).all()
    for old in old_strategies:
        old.status = StrategyStatus.ROLLED_BACK
        session.add(old)
    
    # Create new active one
    payload.workspace_id = workspace_id
    payload.status = StrategyStatus.ACTIVE
    payload.version_number = len(old_strategies) + 1
    session.add(payload)
    session.commit()
    session.refresh(payload)
    return payload
@router.post("/{workspace_id}/leads", response_model=Lead)
def create_lead(
    workspace_id: int, 
    lead: Lead, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    lead.workspace_id = workspace_id
    lead.tenant_id = auth.tenant.id
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead


@router.delete("/{workspace_id}/leads/{lead_id}")
def delete_lead(
    workspace_id: int,
    lead_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")

    lead = session.get(Lead, lead_id)
    if not lead or lead.tenant_id != auth.tenant.id or lead.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Unified messaging cleanup.
    unified_messages = session.exec(
        select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == auth.tenant.id,
            UnifiedMessage.lead_id == lead.id,
        )
    ).all()
    message_ids = [m.id for m in unified_messages if m.id is not None]
    if message_ids:
        queue_rows = session.exec(
            select(OutboundQueue).where(
                OutboundQueue.tenant_id == auth.tenant.id,
                OutboundQueue.message_id.in_(message_ids),
            )
        ).all()
        for row in queue_rows:
            session.delete(row)

    thread_rows = session.exec(
        select(UnifiedThread).where(
            UnifiedThread.tenant_id == auth.tenant.id,
            UnifiedThread.lead_id == lead.id,
        )
    ).all()
    thread_ids = [t.id for t in thread_rows if t.id is not None]
    if thread_ids:
        insight_rows = session.exec(
            select(ThreadInsight).where(
                ThreadInsight.tenant_id == auth.tenant.id,
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
            ConversationThread.tenant_id == auth.tenant.id,
            ConversationThread.lead_id == lead.id,
        )
    ).all()
    legacy_thread_ids = [t.id for t in legacy_threads if t.id is not None]
    if legacy_thread_ids:
        legacy_messages = session.exec(
            select(ChatMessageNew).where(
                ChatMessageNew.tenant_id == auth.tenant.id,
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
            PolicyDecision.tenant_id == auth.tenant.id,
            PolicyDecision.lead_id == lead.id,
        )
    ).all()
    for row in policy_rows:
        session.delete(row)

    memory_row = session.exec(
        select(LeadMemory).where(
            LeadMemory.tenant_id == auth.tenant.id,
            LeadMemory.lead_id == lead.id,
        )
    ).first()
    if memory_row:
        session.delete(memory_row)

    calendar_rows = session.exec(
        select(CalendarEvent).where(
            CalendarEvent.tenant_id == auth.tenant.id,
            CalendarEvent.lead_id == lead.id,
        )
    ).all()
    for row in calendar_rows:
        session.delete(row)

    session.delete(lead)
    session.commit()
    return {"status": "deleted", "lead_id": lead_id}


@router.post("/{workspace_id}/leads/{lead_id}/mode", response_model=Lead)
def set_lead_mode(
    workspace_id: int,
    lead_id: int,
    payload: LeadModeRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")

    lead = session.get(Lead, lead_id)
    if not lead or lead.tenant_id != auth.tenant.id or lead.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    mode = (payload.mode or "").strip().lower()
    tags = [str(t) for t in (lead.tags or []) if str(t) not in {"ON_HOLD", "WORKING"}]
    if mode == "on_hold":
        tags.append("ON_HOLD")
    elif mode == "working":
        tags.append("WORKING")
        if _stage_value(lead.stage) == "NEW":
            lead.stage = "CONTACTED"
        lead.last_followup_review_at = datetime.utcnow()
    else:
        raise HTTPException(status_code=400, detail="mode must be one of: on_hold, working")

    lead.tags = tags
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead
