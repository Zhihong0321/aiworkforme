"""
MODULE: Database Models - Agent
PURPOSE: SQLModel definitions for Agents and Knowledge Files.
"""
from typing import List, Optional
from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel

from .links import AgentMCPServer

class Agent(SQLModel, table=True):
    __tablename__ = "zairag_agents"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    name: str
    system_prompt: str
    # Legacy columns kept for production schema compatibility.
    # Runtime routing remains platform-admin controlled elsewhere.
    model: str = Field(default="glm-4.7-flash")
    reasoning_enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
    )
    # --- Optional behaviour settings ---
    # Mimic casual WhatsApp human typing style
    mimic_human_typing: bool = Field(default=False)
    # Emoji frequency: 'none' | 'low' | 'high'
    emoji_level: str = Field(default="none")
    # Delay (ms) between each segmented message burst
    segment_delay_ms: int = Field(default=800)
    
    chat_sessions: List["ChatSession"] = Relationship(
        back_populates="agent",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    mcp_servers: List["MCPServer"] = Relationship(
        back_populates="agents", link_model=AgentMCPServer
    )
    knowledge_files: List["AgentKnowledgeFile"] = Relationship(
        back_populates="agent",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

class AgentKnowledgeFile(SQLModel, table=True):
    __tablename__ = "zairag_agent_knowledge_files"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    agent_id: int = Field(foreign_key="zairag_agents.id", index=True)
    filename: str
    content: str
    tags: str = Field(default="[]") # JSON Array of strings
    description: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow})
    last_trigger_inputs: str = Field(default="[]") # JSON Array of last 10 queries that matched this file
    
    agent: "Agent" = Relationship(back_populates="knowledge_files")

# DTOs / Read Models
class AgentRead(SQLModel):
    id: Optional[int]
    name: str
    system_prompt: str
    linked_mcp_ids: List[int] = Field(default_factory=list)
    linked_mcp_count: int = 0
    mimic_human_typing: bool = False
    emoji_level: str = "none"
    segment_delay_ms: int = 800
    class Config:
        from_attributes = True

class AgentUpdate(SQLModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    mimic_human_typing: Optional[bool] = None
    emoji_level: Optional[str] = None
    segment_delay_ms: Optional[int] = None
