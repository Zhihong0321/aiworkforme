from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from sqlmodel import SQLModel
from src.infra.database import get_session
from src.adapters.db.crm_models import Workspace, Lead, StrategyVersion, StrategyStatus
from src.adapters.db.agent_models import Agent
from src.adapters.api.dependencies import require_tenant_access, AuthContext

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
