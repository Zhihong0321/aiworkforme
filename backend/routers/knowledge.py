from datetime import datetime
import json
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Form, HTTPException
from sqlmodel import SQLModel, Session

from src.infra.database import get_session
from src.adapters.db.agent_models import AgentKnowledgeFile


router = APIRouter(prefix="/api/v1/knowledge", tags=["Knowledge Vault"])


class KnowledgeFileUpdate(SQLModel):
    filename: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None


@router.put("/{file_id}")
async def update_knowledge_file(
    file_id: int,
    filename: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    session: Session = Depends(get_session),
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

    knowledge_file.updated_at = datetime.utcnow()

    session.add(knowledge_file)
    session.commit()
    session.refresh(knowledge_file)
    return knowledge_file


@router.patch("/{file_id}")
def patch_knowledge_file(
    file_id: int,
    payload: KnowledgeFileUpdate = Body(...),
    session: Session = Depends(get_session),
):
    knowledge_file = session.get(AgentKnowledgeFile, file_id)
    if not knowledge_file:
        raise HTTPException(status_code=404, detail="Knowledge file not found")

    if payload.filename is not None:
        knowledge_file.filename = payload.filename
    if payload.content is not None:
        knowledge_file.content = payload.content
    if payload.tags is not None:
        if not all(isinstance(t, str) for t in payload.tags):
            raise HTTPException(status_code=400, detail="Tags must be an array of strings.")
        knowledge_file.tags = json.dumps(payload.tags)
    if payload.description is not None:
        knowledge_file.description = payload.description

    knowledge_file.updated_at = datetime.utcnow()

    session.add(knowledge_file)
    session.commit()
    session.refresh(knowledge_file)
    return knowledge_file


@router.delete("/{file_id}")
def delete_knowledge_file(file_id: int, session: Session = Depends(get_session)):
    knowledge_file = session.get(AgentKnowledgeFile, file_id)
    if not knowledge_file:
        raise HTTPException(status_code=404, detail="Knowledge file not found")

    session.delete(knowledge_file)
    session.commit()
    return {"message": "File deleted"}
