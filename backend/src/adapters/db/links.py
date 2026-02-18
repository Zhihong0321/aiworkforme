"""
MODULE: Database Models - Relationships
PURPOSE: Link models for many-to-many relationships.
"""
from typing import Optional
from sqlmodel import Field, SQLModel

class AgentMCPServer(SQLModel, table=True):
    __tablename__ = "zairag_agent_mcp_links"
    agent_id: Optional[int] = Field(default=None, foreign_key="zairag_agents.id", primary_key=True)
    mcp_server_id: Optional[int] = Field(
        default=None, foreign_key="zairag_mcp_servers.id", primary_key=True
    )
