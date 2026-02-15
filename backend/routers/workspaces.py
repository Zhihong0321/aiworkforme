from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from database import get_session
from models import Workspace, Agent, Lead, StrategyVersion, StrategyStatus

router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspace Management"])

@router.get("/", response_model=List[Workspace])
def list_workspaces(session: Session = Depends(get_session)):
    return session.exec(select(Workspace)).all()

@router.post("/", response_model=Workspace)
def create_workspace(workspace: Workspace, session: Session = Depends(get_session)):
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace

@router.put("/{workspace_id}", response_model=Workspace)
def update_workspace(workspace_id: int, agent_id: Optional[int] = None, name: Optional[str] = None, session: Session = Depends(get_session)):
    ws = session.get(Workspace, workspace_id)
    if not ws:
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
def get_workspace_leads(workspace_id: int, session: Session = Depends(get_session)):
    from models import Lead
    return session.exec(select(Lead).where(Lead.workspace_id == workspace_id)).all()

@router.get("/{workspace_id}/strategy", response_model=Optional[StrategyVersion])
def get_workspace_strategy(workspace_id: int, session: Session = Depends(get_session)):
    from models import StrategyVersion, StrategyStatus
    return session.exec(
        select(StrategyVersion)
        .where(StrategyVersion.workspace_id == workspace_id)
        .where(StrategyVersion.status == StrategyStatus.ACTIVE)
    ).first()

@router.post("/{workspace_id}/strategy", response_model=StrategyVersion)
def update_workspace_strategy(workspace_id: int, payload: StrategyVersion, session: Session = Depends(get_session)):
    from models import StrategyVersion, StrategyStatus
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
