"""
MODULE: Database Models - Chat
PURPOSE: SQLModel definitions for Chat Sessions and Messages.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel, Column, JSON

class ChatSession(SQLModel, table=True):
    __tablename__ = "zairag_chat_sessions"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    agent_id: int = Field(foreign_key="zairag_agents.id")
    
    total_tokens: int = Field(default=0)
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    agent: "Agent" = Relationship(back_populates="chat_sessions")
    chat_messages: List["ChatMessage"] = Relationship(
        back_populates="chat_session",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

class ChatMessage(SQLModel, table=True):
    __tablename__ = "zairag_chat_messages"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    chat_session_id: int = Field(foreign_key="zairag_chat_sessions.id")
    role: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # New fields for tool support
    tool_calls: Optional[str] = Field(default=None) # JSON string of tool calls list
    tool_call_id: Optional[str] = Field(default=None) # For role='tool', links to call id

    chat_session: "ChatSession" = Relationship(back_populates="chat_messages")

class ChatRequest(SQLModel):
    agent_id: int
    message: str
    include_reasoning: bool = True

class ChatResponse(SQLModel):
    response: str
