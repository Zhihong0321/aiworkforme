"""
MODULE: Database Models - MCP Server
PURPOSE: SQLModel definitions for MCP Server configurations.
"""
from typing import List, Optional
from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel
from .links import AgentMCPServer

class MCPServer(SQLModel, table=True):
    __tablename__ = "zairag_mcp_servers"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    name: str
    script: str
    command: str = Field(default="python")
    args: str = Field(default="[]") # JSON list of args
    cwd: str = Field(default="/app")
    env_vars: str = Field(default="{}") # JSON dict of env vars
    
    # Observability & Metadata
    status: str = Field(default="stopped") # stopped, running, error
    last_heartbeat: Optional[str] = Field(default=None) # ISO format datetime
    last_error: Optional[str] = Field(default=None)
    checksum: Optional[str] = Field(default=None) # SHA256
    size_bytes: Optional[int] = Field(default=None)
    
    agents: List["Agent"] = Relationship(
        back_populates="mcp_servers", link_model=AgentMCPServer
    )
