"""
MODULE: Database Models - CRM / Masterplan
PURPOSE: SQLModel definitions for Leads, Workspaces, Strategies, and Memories.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from sqlmodel import Field, Relationship, SQLModel, Column, JSON

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
    whatsapp_lid: Optional[str] = Field(default=None, index=True)
    is_whatsapp_valid: Optional[bool] = Field(default=None, index=True)
    last_verify_at: Optional[datetime] = None
    verify_error: Optional[str] = None
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
    channel_session_id: Optional[int] = Field(default=None, foreign_key="et_channel_sessions.id", index=True)  # Multi-channel support
    
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    lead: "Lead" = Relationship(back_populates="threads")
    messages: List["ChatMessageNew"] = Relationship(back_populates="thread")
    channel_session: Optional["ChannelSession"] = Relationship(back_populates="threads")

class ChatMessageNew(SQLModel, table=True):
    __tablename__ = "et_chat_messages"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    thread_id: int = Field(foreign_key="et_conversation_threads.id", index=True)
    
    # Multi-channel fields
    channel_message_id: str = Field(max_length=255, index=True)  # Original message ID from channel (for idempotency)
    channel_timestamp: int  # Unix epoch milliseconds from channel
    direction: str = Field(max_length=20, index=True)  # 'inbound' or 'outbound'
    sender_identifier: Optional[str] = Field(default=None, max_length=255)  # Phone/email of sender
    message_type: str = Field(default="text", max_length=50)  # 'text', 'image', 'video', 'audio', 'document'
    
    # Content fields
    role: str  # user, assistant, system
    content: Optional[str] = None  # Text content (can be NULL for media-only messages)
    
    # Media fields
    media_url: Optional[str] = None  # URL to media file if applicable
    media_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))  # {filename, mime_type, size, caption}
    
    # Technical fields
    tool_calls: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))  # For AI assistant messages
    raw_payload: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))  # Full original message object from channel
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    
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
