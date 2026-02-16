from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from sqlmodel import Field, Relationship, SQLModel, Column, JSON
from sqlalchemy import UniqueConstraint


class Role(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    TENANT_ADMIN = "tenant_admin"
    TENANT_USER = "tenant_user"


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Tenant(SQLModel, table=True):
    __tablename__ = "et_tenants"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    status: TenantStatus = Field(default=TenantStatus.ACTIVE)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    memberships: List["TenantMembership"] = Relationship(back_populates="tenant")


class User(SQLModel, table=True):
    __tablename__ = "et_users"
    __table_args__ = (UniqueConstraint("email", name="uq_et_users_email"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    password_hash: str
    is_active: bool = Field(default=True)
    is_platform_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None

    memberships: List["TenantMembership"] = Relationship(back_populates="user")


class TenantMembership(SQLModel, table=True):
    __tablename__ = "et_tenant_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_et_tenant_memberships_user_tenant"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="et_users.id", index=True)
    tenant_id: int = Field(foreign_key="et_tenants.id", index=True)
    role: Role = Field(default=Role.TENANT_USER)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: "User" = Relationship(back_populates="memberships")
    tenant: "Tenant" = Relationship(back_populates="memberships")


class AdminAuditLog(SQLModel, table=True):
    __tablename__ = "et_admin_audit_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: int = Field(foreign_key="et_users.id", index=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    action: str = Field(index=True)
    target_type: str
    target_id: Optional[str] = None
    details: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class SecurityEventLog(SQLModel, table=True):
    __tablename__ = "et_security_events"
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: Optional[int] = Field(default=None, foreign_key="et_users.id", index=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    event_type: str = Field(index=True)
    endpoint: str
    method: str
    status_code: int = Field(index=True)
    reason: str = Field(index=True)
    details: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class SystemSetting(SQLModel, table=True):
    __tablename__ = "zairag_system_settings"
    key: str = Field(primary_key=True)
    value: str

class AgentMCPServer(SQLModel, table=True):
    __tablename__ = "zairag_agent_mcp_links"
    agent_id: Optional[int] = Field(default=None, foreign_key="zairag_agents.id", primary_key=True)
    mcp_server_id: Optional[int] = Field(
        default=None, foreign_key="zairag_mcp_servers.id", primary_key=True
    )


class Agent(SQLModel, table=True):
    __tablename__ = "zairag_agents"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    name: str
    system_prompt: str
    model: str
    reasoning_enabled: bool = Field(default=True)

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


class AgentRead(SQLModel):
    """
    Lightweight response model for agent listings that includes MCP linkage info.
    """

    id: Optional[int]
    name: str
    system_prompt: str
    model: str
    reasoning_enabled: bool = True

    linked_mcp_ids: List[int] = Field(default_factory=list)
    linked_mcp_count: int = 0

    class Config:
        from_attributes = True


class AgentUpdate(SQLModel):
    """Payload for updating an agent."""

    name: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    reasoning_enabled: Optional[bool] = None


class AgentKnowledgeFile(SQLModel, table=True):
    __tablename__ = "zairag_agent_knowledge_files"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    agent_id: int = Field(foreign_key="zairag_agents.id")
    filename: str
    content: str
    tags: str = Field(default="[]") # JSON Array of strings
    description: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow})
    last_trigger_inputs: str = Field(default="[]") # JSON Array of last 10 queries that matched this file

    agent: "Agent" = Relationship(back_populates="knowledge_files")


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


# --- Masterplan MVP Domain Models ---

class LeadStage(str, Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    ENGAGED = "ENGAGED"
    QUALIFIED = "QUALIFIED"
    OUTCOME_APPOINTMENT = "OUTCOME_APPOINTMENT"
    OUTCOME_PURCHASE = "OUTCOME_PURCHASE"
    TAKE_OVER = "TAKE_OVER"
    CLOSED_LOST = "CLOSED_LOST"
    SUPPRESSED = "SUPPRESSED"

class LeadTag(str, Enum):
    NO_RESPONSE = "NO_RESPONSE"
    NEUTRAL = "NEUTRAL"
    POSITIVE = "POSITIVE"
    RESISTIVE = "RESISTIVE"
    DISCONNECT = "DISCONNECT"
    STRATEGY_REVIEW_REQUIRED = "STRATEGY_REVIEW_REQUIRED"
    INTENT_APPOINTMENT = "INTENT_APPOINTMENT"
    INTENT_PURCHASE = "INTENT_PURCHASE"

class BudgetTier(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"

class FollowUpPreset(str, Enum):
    GENTLE = "GENTLE"
    BALANCED = "BALANCED"
    AGGRESSIVE = "AGGRESSIVE"

class StrategyStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ROLLED_BACK = "ROLLED_BACK"

class Workspace(SQLModel, table=True):
    __tablename__ = "et_workspaces"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    name: str
    timezone: str = Field(default="UTC")
    budget_tier: BudgetTier = Field(default=BudgetTier.GREEN)
    agent_id: Optional[int] = Field(default=None, foreign_key="zairag_agents.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    leads: List["Lead"] = Relationship(back_populates="workspace")
    strategies: List["StrategyVersion"] = Relationship(back_populates="workspace")

class StrategyVersion(SQLModel, table=True):
    __tablename__ = "et_strategy_versions"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    workspace_id: int = Field(foreign_key="et_workspaces.id")
    version_number: int
    status: StrategyStatus = Field(default=StrategyStatus.DRAFT)
    
    # Strategy Content
    tone: str
    objectives: str
    objection_handling: str
    cta_rules: str
    
    # Intervals / Aggressiveness
    followup_preset: FollowUpPreset = Field(default=FollowUpPreset.BALANCED)
    interval_overrides: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    activated_at: Optional[datetime] = None
    
    workspace: "Workspace" = Relationship(back_populates="strategies")

class Lead(SQLModel, table=True):
    __tablename__ = "et_leads"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    workspace_id: int = Field(foreign_key="et_workspaces.id")
    external_id: str = Field(index=True) # e.g. Phone number/WhatsApp ID
    name: Optional[str] = None
    
    stage: LeadStage = Field(default=LeadStage.NEW)
    tags: List[str] = Field(default=[], sa_column=Column(JSON)) # List of LeadTag strings
    
    # Metadata
    timezone: Optional[str] = None
    last_followup_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    last_followup_review_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    workspace: "Workspace" = Relationship(back_populates="leads")
    threads: List["ConversationThread"] = Relationship(back_populates="lead")

class ConversationThread(SQLModel, table=True):
    __tablename__ = "et_conversation_threads"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    workspace_id: int = Field(foreign_key="et_workspaces.id")
    lead_id: int = Field(foreign_key="et_leads.id")
    
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    lead: "Lead" = Relationship(back_populates="threads")
    messages: List["ChatMessageNew"] = Relationship(back_populates="thread")

class ChatMessageNew(SQLModel, table=True):
    __tablename__ = "et_chat_messages"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    thread_id: int = Field(foreign_key="et_conversation_threads.id")
    role: str # user, model, system
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    thread: "ConversationThread" = Relationship(back_populates="messages")

class PolicyDecision(SQLModel, table=True):
    __tablename__ = "et_policy_decisions"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    workspace_id: int = Field(foreign_key="et_workspaces.id")
    lead_id: int = Field(foreign_key="et_leads.id")
    
    allow_send: bool
    reason_code: str
    rule_trace: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    next_allowed_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class OutreachAttestation(SQLModel, table=True):
    __tablename__ = "et_outreach_attestations"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    workspace_id: int = Field(foreign_key="et_workspaces.id")
    operator_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    granted: bool = True

class LeadMemory(SQLModel, table=True):
    __tablename__ = "et_lead_memories"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    lead_id: int = Field(foreign_key="et_leads.id", unique=True)
    
    # Rolling summary of the last conversation
    summary: Optional[str] = None
    
    # Key facts extracted from conversation (JSON list of facts)
    facts: List[str] = Field(default=[], sa_column=Column(JSON))
    
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)


# --- Request models for prototype compatibility ---

class SpawnMCPRequest(SQLModel):
    command: str
    args: List[str]
    cwd: str = "/app"

class ChatRequest(SQLModel):
    agent_id: int
    message: str
    include_reasoning: bool = True

class ChatResponse(SQLModel):
    response: str

