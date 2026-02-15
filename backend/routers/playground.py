from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Dict, Any, Optional
from database import get_session
from models import Lead, Workspace, ConversationThread, ChatMessageNew, PolicyDecision
from runtime.agent_runtime import ConversationAgentRuntime
from dependencies import zai_client
from providers.uniapi import UniAPIClient

router = APIRouter(prefix="/api/v1/playground", tags=["Playground"])

def get_uniapi_client():
    return zai_client

@router.get("/workspaces", response_model=List[Workspace])
async def get_workspaces(session: Session = Depends(get_session)):
    return session.exec(select(Workspace)).all()

@router.get("/leads", response_model=List[Lead])
async def get_leads(workspace_id: Optional[int] = None, session: Session = Depends(get_session)):
    statement = select(Lead)
    if workspace_id:
        statement = statement.where(Lead.workspace_id == workspace_id)
    return session.exec(statement).all()

@router.post("/chat")
async def playground_chat(
    lead_id: int,
    workspace_id: int,
    message: str,
    session: Session = Depends(get_session),
    client: ZaiClient = Depends(get_uniapi_client)
):
    if not client.is_configured:
        raise HTTPException(status_code=503, detail="AI Provider not configured. Set the key in Settings.")
    runtime = ConversationAgentRuntime(session, client)
    
    # We want to capture the trace, so we might need to modify run_turn or just fetch decisions after
    result = await runtime.run_turn(lead_id=lead_id, workspace_id=workspace_id, user_message=message)
    
    # Fetch the latest policy decisions for this lead to show in the inspector
    decisions = session.exec(
        select(PolicyDecision)
        .where(PolicyDecision.lead_id == lead_id)
        .order_by(PolicyDecision.created_at.desc())
        .limit(5)
    ).all()
    
    return {
        "result": result,
        "decisions": decisions
    }

@router.get("/thread/{lead_id}")
async def get_thread_messages(lead_id: int, session: Session = Depends(get_session)):
    thread = session.exec(
        select(ConversationThread)
        .where(ConversationThread.lead_id == lead_id)
        .where(ConversationThread.status == "active")
    ).first()
    
    if not thread:
        return []
    
    messages = session.exec(
        select(ChatMessageNew)
        .where(ChatMessageNew.thread_id == thread.id)
        .order_by(ChatMessageNew.created_at.asc())
    ).all()
    
    return messages
