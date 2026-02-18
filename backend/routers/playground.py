from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, SQLModel
from typing import List, Dict, Any, Optional
from src.infra.database import get_session
from src.adapters.db.crm_models import Lead, Workspace, ConversationThread, ChatMessageNew, PolicyDecision
from src.adapters.api.dependencies import get_llm_router, require_tenant_access, AuthContext
from src.infra.llm.router import LLMRouter
from src.app.runtime.agent_runtime import ConversationAgentRuntime

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/playground", tags=["Playground"])
LEGACY_MESSAGING_WRITE_DISABLED_DETAIL = (
    "Legacy messaging writes are disabled. Use /api/v1/messaging canonical endpoints."
)

class ChatRequest(SQLModel):
    lead_id: Optional[int] = None
    workspace_id: Optional[int] = None
    message: str
    agent_id: Optional[int] = None

@router.get("/workspaces", response_model=List[Workspace])
async def get_workspaces(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    statement = select(Workspace).where(Workspace.tenant_id == auth.tenant.id)
    return session.exec(statement).all()

@router.get("/leads", response_model=List[Lead])
async def get_leads(
    workspace_id: Optional[int] = None, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    statement = select(Lead).where(Lead.tenant_id == auth.tenant.id)
    if workspace_id:
        statement = statement.where(Lead.workspace_id == workspace_id)
    return session.exec(statement).all()

@router.post("/chat")
async def playground_chat(
    request: ChatRequest,
    session: Session = Depends(get_session),
    router: LLMRouter = Depends(get_llm_router),
    auth: AuthContext = Depends(require_tenant_access)
):
    raise HTTPException(status_code=410, detail=LEGACY_MESSAGING_WRITE_DISABLED_DETAIL)
    import traceback
    try:
        # 1. Ensure we have a Workspace. If none provided, find or create one for this tenant.
        ws_id = request.workspace_id
        if not ws_id:
            workspace = session.exec(select(Workspace).where(Workspace.tenant_id == auth.tenant.id)).first()
            if not workspace:
                workspace = Workspace(name="Default Workspace", tenant_id=auth.tenant.id)
                session.add(workspace)
                session.commit()
                session.refresh(workspace)
            ws_id = workspace.id
        else:
            # Validate existing
            workspace = session.exec(select(Workspace).where(Workspace.id == ws_id, Workspace.tenant_id == auth.tenant.id)).first()
            if not workspace:
                raise HTTPException(status_code=403, detail="Invalid workspace")

        # 2. Ensure we have a Lead. Playground = User = Tester Lead.
        lead_id = request.lead_id
        if not lead_id:
            # Use a consistent 'external_id' for the playground tester
            lead = session.exec(select(Lead).where(
                Lead.tenant_id == auth.tenant.id, 
                Lead.external_id == f"playground_{auth.user.id}"
            )).first()
            
            if not lead:
                lead = Lead(
                    tenant_id=auth.tenant.id,
                    workspace_id=ws_id,
                    external_id=f"playground_{auth.user.id}",
                    name=f"Tester ({auth.user.email})",
                    stage="NEW"
                )
                session.add(lead)
                session.commit()
                session.refresh(lead)
            lead_id = lead.id
        else:
            # Validate existing
            lead = session.exec(select(Lead).where(Lead.id == lead_id, Lead.tenant_id == auth.tenant.id)).first()
            if not lead:
                raise HTTPException(status_code=403, detail="Invalid lead")

        runtime = ConversationAgentRuntime(session, router)
        
        result = await runtime.run_turn(
            lead_id=lead_id, 
            workspace_id=ws_id, 
            user_message=request.message,
            agent_id_override=request.agent_id,
            bypass_safety=True
        )
        
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
    except Exception as e:
        logger.error(f"PLAYGROUND CHAT ERROR: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

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

@router.post("/thread/{lead_id}/reset")
async def reset_playground_thread(
    lead_id: int, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    raise HTTPException(status_code=410, detail=LEGACY_MESSAGING_WRITE_DISABLED_DETAIL)
    # Verify lead access
    lead = session.exec(select(Lead).where(Lead.id == lead_id, Lead.tenant_id == auth.tenant.id)).first()
    if not lead:
        raise HTTPException(status_code=403, detail="Invalid lead")

    # Find active thread
    thread = session.exec(
        select(ConversationThread)
        .where(ConversationThread.lead_id == lead_id)
        .where(ConversationThread.status == "active")
    ).first()
    
    if thread:
        thread.status = "archived"
        session.add(thread)
        session.commit()
    
    # Create new thread
    new_thread = ConversationThread(
        lead_id=lead_id,
        workspace_id=lead.workspace_id,
        tenant_id=auth.tenant.id,
        status="active"
    )
    session.add(new_thread)
    session.commit()
    session.refresh(new_thread)
    
    return {"status": "success", "thread_id": new_thread.id}
