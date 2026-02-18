from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from sqlmodel import Session, select
from database import get_session
from models import PolicyDecision

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/policy", tags=["Policy"])

@router.get("/decisions", response_model=List[PolicyDecision])
async def get_policy_decisions(
    workspace_id: int,
    lead_id: Optional[int] = None,
    session: Session = Depends(get_session)
):
    """
    Retrieve audit traces of policy decisions for a workspace.
    """
    statement = select(PolicyDecision).where(PolicyDecision.workspace_id == workspace_id)
    if lead_id:
        statement = statement.where(PolicyDecision.lead_id == lead_id)
    
    statement = statement.order_by(PolicyDecision.created_at.desc()).limit(100)
    decisions = session.exec(statement).all()
    return decisions
