from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session, select
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
import json
from datetime import datetime

from database import get_session
from models import Agent, AgentMCPServer, MCPServer, AgentKnowledgeFile, AgentRead, AgentUpdate

router = APIRouter(prefix="/api/v1/agents", tags=["Agent Management"])

@router.get("/", response_model=List[AgentRead])
def list_agents(session: Session = Depends(get_session)):
    agents = session.exec(select(Agent)).all()
    results: List[AgentRead] = []

    for agent in agents:
        linked_ids = [
            link_id
            for link_id in session.exec(
                select(AgentMCPServer.mcp_server_id).where(AgentMCPServer.agent_id == agent.id)
            ).all()
            if link_id is not None
        ]

        agent_data = agent.dict(exclude={"chat_sessions", "mcp_servers", "knowledge_files"})
        results.append(
            AgentRead(
                **agent_data,
                linked_mcp_ids=linked_ids,
                linked_mcp_count=len(linked_ids)
            )
        )

    return results

@router.post("/", response_model=Agent)
def create_agent(agent: Agent, session: Session = Depends(get_session)):
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent

@router.put("/{agent_id}", response_model=Agent)
def update_agent(agent_id: int, payload: AgentUpdate, session: Session = Depends(get_session)):
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if payload.name is not None:
        agent.name = payload.name
    if payload.system_prompt is not None:
        agent.system_prompt = payload.system_prompt
    if payload.model is not None:
        agent.model = payload.model

    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent

@router.delete("/{agent_id}")
def delete_agent(agent_id: int, session: Session = Depends(get_session)):
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    session.delete(agent)
    session.commit()
    return {"message": "Agent deleted"}

@router.post("/{agent_id}/link-mcp/{server_id}")
def link_mcp_to_agent(agent_id: int, server_id: int, session: Session = Depends(get_session)):
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    server = session.get(MCPServer, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found")

    # Idempotent link: skip duplicates instead of throwing 500 on unique constraint
    existing_link = session.get(AgentMCPServer, (agent_id, server_id))
    if existing_link:
        return {"message": "MCP already linked to agent"}

    link = AgentMCPServer(agent_id=agent_id, mcp_server_id=server_id)
    session.add(link)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # Likely duplicate link raced in; treat as success to keep UI happy
        return {"message": "MCP already linked to agent"}

    return {"message": "Linked successfully"}

@router.post("/{agent_id}/knowledge")
async def upload_agent_knowledge(
    agent_id: int,
    file: UploadFile = File(...),
    tags: Optional[str] = Form(default="[]"),
    description: Optional[str] = Form(default=""),
    session: Session = Depends(get_session)
):
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    content = await file.read()
    try:
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
         raise HTTPException(status_code=400, detail="File must be valid UTF-8 text")

    # Validate and parse tags JSON
    try:
        parsed_tags = json.loads(tags)
        if not isinstance(parsed_tags, list) or not all(isinstance(t, str) for t in parsed_tags):
            raise ValueError("Tags must be a JSON array of strings.")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Tags must be a valid JSON array string.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    knowledge = AgentKnowledgeFile(
        agent_id=agent_id,
        filename=file.filename,
        content=content_str,
        tags=tags, # Store as JSON string
        description=description,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_trigger_inputs="[]" # Initialize as empty JSON array string
    )
    session.add(knowledge)
    session.commit()
    session.refresh(knowledge)
    return knowledge

@router.get("/{agent_id}/knowledge", response_model=List[AgentKnowledgeFile])
def list_agent_knowledge(agent_id: int, session: Session = Depends(get_session)):
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    files = session.exec(select(AgentKnowledgeFile).where(AgentKnowledgeFile.agent_id == agent_id)).all()
    return files

@router.put("/knowledge/{file_id}")
async def update_agent_knowledge(
    file_id: int,
    filename: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    knowledge_file = session.get(AgentKnowledgeFile, file_id)
    if not knowledge_file:
        raise HTTPException(status_code=404, detail="Knowledge file not found")

    if filename is not None:
        knowledge_file.filename = filename
    if content is not None:
        knowledge_file.content = content
    if tags is not None:
        try:
            parsed_tags = json.loads(tags)
            if not isinstance(parsed_tags, list) or not all(isinstance(t, str) for t in parsed_tags):
                raise ValueError("Tags must be a JSON array of strings.")
            knowledge_file.tags = tags
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Tags must be a valid JSON array string.")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    if description is not None:
        knowledge_file.description = description

    knowledge_file.updated_at = datetime.utcnow() # Update timestamp

    session.add(knowledge_file)
    session.commit()
    session.refresh(knowledge_file)
    return knowledge_file

@router.delete("/{agent_id}/knowledge/{file_id}")
def delete_agent_knowledge(agent_id: int, file_id: int, session: Session = Depends(get_session)):
    file = session.get(AgentKnowledgeFile, file_id)
    if not file or file.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="File not found for this agent")
    
    session.delete(file)
    session.commit()
    return {"message": "File deleted"}
