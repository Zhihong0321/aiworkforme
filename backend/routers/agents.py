from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlmodel import Session, select
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel

from src.infra.database import get_session
from src.adapters.api.dependencies import require_tenant_access, AuthContext, get_llm_router
from src.adapters.db.agent_models import (
    Agent,
    AgentKnowledgeFile,
    AgentMCPServer,
    AgentRead,
    AgentSalesMaterial,
    AgentUpdate,
)
from src.adapters.db.channel_models import ChannelSession, ChannelType
from src.adapters.db.mcp_models import MCPServer
from src.app.runtime.knowledge_processor import KnowledgeProcessor
from src.app.runtime.sales_materials import (
    build_sales_material_public_url,
    build_sales_material_stored_name,
    build_url_sales_material,
    delete_sales_material_file,
    list_agent_sales_materials as _list_agent_sales_materials,
    serialize_sales_material,
    validate_sales_material_upload,
    write_sales_material_file,
)
from src.infra.llm.router import LLMRouter
from src.adapters.db.crm_models import AICRMThreadState, AgentCRMProfile, Lead, Workspace
from src.adapters.db.messaging_models import UnifiedThread
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["Agent Management"])


class AgentCreate(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    mimic_human_typing: Optional[bool] = False
    emoji_level: Optional[str] = "none"
    segment_delay_ms: Optional[int] = 800
    preferred_channel_session_id: Optional[int] = None


class AgentSalesMaterialRead(BaseModel):
    id: int
    agent_id: int
    filename: str
    media_type: str
    kind: str
    source_type: str
    external_url: Optional[str] = None
    file_size_bytes: int
    description: str
    public_url: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AgentSalesMaterialLinkCreate(BaseModel):
    url: str
    description: str


def _validate_preferred_channel_session(
    session: Session,
    tenant_id: int,
    preferred_channel_session_id: Optional[int],
    current_agent_id: Optional[int] = None,
) -> Optional[int]:
    if preferred_channel_session_id is None:
        return None

    channel_session = session.get(ChannelSession, preferred_channel_session_id)
    if (
        not channel_session
        or channel_session.tenant_id != tenant_id
        or channel_session.channel_type != ChannelType.WHATSAPP
    ):
        raise HTTPException(status_code=400, detail="Preferred WhatsApp channel is invalid")

    conflict = session.exec(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.preferred_channel_session_id == preferred_channel_session_id,
            Agent.id != current_agent_id,
        )
    ).first()
    if conflict:
        conflict_name = (conflict.name or "").strip() or f"Agent #{conflict.id}"
        raise HTTPException(
            status_code=400,
            detail=f"WhatsApp channel is already assigned to {conflict_name}. One channel can only belong to one agent.",
        )

    return int(channel_session.id)

@router.get("/", response_model=List[AgentRead])
def list_agents(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    import traceback
    try:
        agents = session.exec(select(Agent).where(Agent.tenant_id == auth.tenant.id)).all()
        results: List[AgentRead] = []

        for agent in agents:
            linked_ids = [
                link_id
                for link_id in session.exec(
                    select(AgentMCPServer.mcp_server_id).where(AgentMCPServer.agent_id == agent.id)
                ).all()
                if link_id is not None
            ]

            # Use model_dump in Pydantic v2 or dict in v1
            agent_data = agent.model_dump(
                exclude={"chat_sessions", "mcp_servers", "knowledge_files", "sales_materials", "model", "reasoning_enabled"}
            )
            results.append(
                AgentRead(
                    **agent_data,
                    linked_mcp_ids=linked_ids,
                    linked_mcp_count=len(linked_ids)
                )
            )

        return results
    except Exception as e:
        logger.error(f"LIST AGENTS ERROR: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=AgentRead)
def create_agent(
    agent_in: AgentCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    name = (agent_in.name or "").strip() or "New Agent"
    system_prompt = (agent_in.system_prompt or "").strip()

    new_agent = Agent(
        name=name,
        system_prompt=system_prompt,
        tenant_id=auth.tenant.id,
        created_at=datetime.utcnow(),
        mimic_human_typing=bool(agent_in.mimic_human_typing or False),
        emoji_level=str(agent_in.emoji_level or "none"),
        segment_delay_ms=int(agent_in.segment_delay_ms or 800),
        preferred_channel_session_id=_validate_preferred_channel_session(
            session,
            auth.tenant.id,
            agent_in.preferred_channel_session_id,
            current_agent_id=None,
        ),
    )
    
    session.add(new_agent)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Invalid agent payload") from exc
    except Exception:
        session.rollback()
        logger.exception("CREATE AGENT ERROR")
        raise HTTPException(status_code=500, detail="Failed to create agent")
    session.refresh(new_agent)
    
    return AgentRead(
        id=new_agent.id,
        name=new_agent.name,
        system_prompt=new_agent.system_prompt,
        linked_mcp_ids=[],
        linked_mcp_count=0,
        mimic_human_typing=new_agent.mimic_human_typing,
        emoji_level=new_agent.emoji_level,
        segment_delay_ms=new_agent.segment_delay_ms,
        preferred_channel_session_id=new_agent.preferred_channel_session_id,
    )

@router.put("/{agent_id}", response_model=AgentRead)
def update_agent(
    agent_id: int, 
    payload: AgentUpdate, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")

    if payload.name is not None:
        agent.name = payload.name
    if payload.system_prompt is not None:
        agent.system_prompt = payload.system_prompt
    if payload.mimic_human_typing is not None:
        agent.mimic_human_typing = payload.mimic_human_typing
    if payload.emoji_level is not None:
        agent.emoji_level = payload.emoji_level
    if payload.segment_delay_ms is not None:
        agent.segment_delay_ms = payload.segment_delay_ms
    fields_set = getattr(payload, "model_fields_set", None) or getattr(payload, "__fields_set__", set())
    if "preferred_channel_session_id" in fields_set:
        agent.preferred_channel_session_id = _validate_preferred_channel_session(
            session,
            auth.tenant.id,
            payload.preferred_channel_session_id,
            current_agent_id=agent.id,
        )

    session.add(agent)
    session.commit()
    session.refresh(agent)
    linked_ids = session.exec(
        select(AgentMCPServer.mcp_server_id).where(AgentMCPServer.agent_id == agent.id)
    ).all()
    return AgentRead(
        **agent.model_dump(
            exclude={"chat_sessions", "mcp_servers", "knowledge_files", "sales_materials", "model", "reasoning_enabled"}
        ),
        linked_mcp_ids=list(linked_ids),
        linked_mcp_count=len(linked_ids),
    )

@router.get("/{agent_id}", response_model=AgentRead)
def get_agent(
    agent_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    linked_ids = session.exec(
        select(AgentMCPServer.mcp_server_id).where(AgentMCPServer.agent_id == agent.id)
    ).all()

    return AgentRead(
        **agent.model_dump(
            exclude={"chat_sessions", "mcp_servers", "knowledge_files", "sales_materials", "model", "reasoning_enabled"}
        ),
        linked_mcp_ids=list(linked_ids),
        linked_mcp_count=len(linked_ids)
    )

@router.delete("/{agent_id}")
def delete_agent(
    agent_id: int, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")

    materials = _list_agent_sales_materials(session, auth.tenant.id, agent_id)
    for material in materials:
        delete_sales_material_file(material)

    links = session.exec(
        select(AgentMCPServer).where(AgentMCPServer.agent_id == agent_id)
    ).all()
    for link in links:
        session.delete(link)

    crm_profiles = session.exec(
        select(AgentCRMProfile).where(
            AgentCRMProfile.tenant_id == auth.tenant.id,
            AgentCRMProfile.agent_id == agent_id,
        )
    ).all()
    for profile in crm_profiles:
        session.delete(profile)

    crm_thread_states = session.exec(
        select(AICRMThreadState).where(
            AICRMThreadState.tenant_id == auth.tenant.id,
            AICRMThreadState.agent_id == agent_id,
        )
    ).all()
    for state in crm_thread_states:
        session.delete(state)

    workspaces = session.exec(
        select(Workspace).where(
            Workspace.tenant_id == auth.tenant.id,
            Workspace.agent_id == agent_id,
        )
    ).all()
    for workspace in workspaces:
        workspace.agent_id = None
        session.add(workspace)

    leads = session.exec(
        select(Lead).where(
            Lead.tenant_id == auth.tenant.id,
            Lead.agent_id == agent_id,
        )
    ).all()
    for lead in leads:
        lead.agent_id = None
        session.add(lead)

    threads = session.exec(
        select(UnifiedThread).where(
            UnifiedThread.tenant_id == auth.tenant.id,
            UnifiedThread.agent_id == agent_id,
        )
    ).all()
    for thread in threads:
        thread.agent_id = None
        session.add(thread)

    session.delete(agent)
    session.commit()
    return {"message": "Agent deleted"}

@router.post("/{agent_id}/link-mcp/{server_id}")
def link_mcp_to_agent(
    agent_id: int, 
    server_id: int, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    server = session.get(MCPServer, server_id)
    if not server or server.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="MCP Server not found")

    existing_link = session.get(AgentMCPServer, (agent_id, server_id))
    if existing_link:
        return {"message": "MCP already linked to agent"}

    link = AgentMCPServer(agent_id=agent_id, mcp_server_id=server_id)
    session.add(link)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return {"message": "MCP already linked to agent"}

    return {"message": "Linked successfully"}


@router.delete("/{agent_id}/link-mcp/{server_id}")
def unlink_mcp_from_agent(
    agent_id: int,
    server_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")

    server = session.get(MCPServer, server_id)
    if not server or server.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="MCP Server not found")

    link = session.get(AgentMCPServer, (agent_id, server_id))
    if not link:
        return {"message": "MCP already unlinked"}

    session.delete(link)
    session.commit()
    return {"message": "Unlinked successfully"}


@router.get("/{agent_id}/sales-materials", response_model=List[AgentSalesMaterialRead])
def list_agent_sales_materials(
    agent_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")

    materials = _list_agent_sales_materials(session, auth.tenant.id, agent_id)
    return [AgentSalesMaterialRead(**serialize_sales_material(item)) for item in materials]


@router.post("/{agent_id}/sales-materials", response_model=AgentSalesMaterialRead)
async def upload_agent_sales_material(
    agent_id: int,
    request: Request,
    file: UploadFile = File(...),
    description: str = Form(...),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")

    description_text = (description or "").strip()
    if not description_text:
        raise HTTPException(status_code=400, detail="Description is required")

    content = await file.read()
    validated = validate_sales_material_upload(file.filename or "material", file.content_type or "", content)
    public_token = uuid4().hex
    stored_name = build_sales_material_stored_name(
        validated["filename"],
        validated["suffix"],
        public_token=public_token,
    )
    public_url = build_sales_material_public_url(public_token, request=request)

    material = AgentSalesMaterial(
        tenant_id=auth.tenant.id,
        agent_id=agent_id,
        filename=validated["filename"],
        stored_name=stored_name,
        media_type=validated["media_type"],
        source_type=validated.get("source_type") or "file",
        external_url=validated.get("external_url") or "",
        file_size_bytes=validated["file_size_bytes"],
        description=description_text[:1000],
        public_token=public_token,
        public_url=public_url,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(material)
    session.commit()
    session.refresh(material)

    try:
        write_sales_material_file(material, content)
    except Exception as exc:
        session.delete(material)
        session.commit()
        logger.exception("Failed to store sales material for agent_id=%s", agent_id)
        raise HTTPException(status_code=500, detail=f"Failed to store sales material: {exc}") from exc

    return AgentSalesMaterialRead(**serialize_sales_material(material))


@router.post("/{agent_id}/sales-materials/link", response_model=AgentSalesMaterialRead)
def create_agent_sales_material_link(
    agent_id: int,
    payload: AgentSalesMaterialLinkCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")

    description_text = (payload.description or "").strip()
    if not description_text:
        raise HTTPException(status_code=400, detail="Description is required")

    validated = build_url_sales_material(payload.url, description_text)
    material = AgentSalesMaterial(
        tenant_id=auth.tenant.id,
        agent_id=agent_id,
        filename=validated["filename"],
        stored_name="",
        media_type=validated["media_type"],
        source_type=validated["source_type"],
        external_url=validated["external_url"],
        file_size_bytes=validated["file_size_bytes"],
        description=description_text[:1000],
        public_token="",
        public_url=validated["external_url"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(material)
    session.commit()
    session.refresh(material)
    return AgentSalesMaterialRead(**serialize_sales_material(material))


@router.delete("/{agent_id}/sales-materials/{material_id}")
def delete_agent_sales_material(
    agent_id: int,
    material_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    material = session.get(AgentSalesMaterial, material_id)
    if not material or material.agent_id != agent_id or material.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Sales material not found")

    delete_sales_material_file(material)
    session.delete(material)
    session.commit()
    return {"message": "Sales material deleted"}

@router.post("/{agent_id}/knowledge")
async def upload_agent_knowledge(
    agent_id: int,
    file: UploadFile = File(...),
    tags: Optional[str] = Form(default="[]"),
    description: Optional[str] = Form(default=""),
    session: Session = Depends(get_session),
    llm: LLMRouter = Depends(get_llm_router),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")

    content_bytes = await file.read()
    content_str = ""
    
    if file.content_type.startswith("image/"):
        processor = KnowledgeProcessor(session, llm)
        content_str = await processor.process_image(content_bytes, file.filename)
    elif file.content_type == "application/pdf":
        processor = KnowledgeProcessor(session, llm)
        content_str = await processor.process_pdf(content_bytes, file.filename)
    else:
        try:
            content_str = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
             raise HTTPException(status_code=400, detail="Text file must be valid UTF-8")

    knowledge = AgentKnowledgeFile(
        agent_id=agent_id,
        tenant_id=auth.tenant.id,
        filename=file.filename,
        content=content_str,
        tags=tags,
        description=description,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(knowledge)
    session.commit()
    session.refresh(knowledge)
    return knowledge

@router.get("/{agent_id}/knowledge", response_model=List[AgentKnowledgeFile])
def list_agent_knowledge(
    agent_id: int, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    files = session.exec(select(AgentKnowledgeFile).where(AgentKnowledgeFile.agent_id == agent_id)).all()
    return files

@router.delete("/{agent_id}/knowledge/{file_id}")
def delete_agent_knowledge(
    agent_id: int, 
    file_id: int, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    file = session.get(AgentKnowledgeFile, file_id)
    if not file or file.agent_id != agent_id or file.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="File not found or access denied")
    
    session.delete(file)
    session.commit()
    return {"message": "File deleted"}


@router.get("/{agent_id}/leads", response_model=List[Lead])
def list_agent_leads(
    agent_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    leads = session.exec(select(Lead).where(
        Lead.tenant_id == auth.tenant.id,
        Lead.agent_id == agent_id
    )).all()
    return leads


@router.post("/{agent_id}/leads", response_model=Lead)
def create_agent_lead(
    agent_id: int,
    lead: Lead,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    agent = session.get(Agent, agent_id)
    if not agent or agent.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    lead.tenant_id = auth.tenant.id
    lead.agent_id = agent_id
    lead.workspace_id = None
    
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead
