"""
MODULE: Database Models - Unified Messaging
PURPOSE: Canonical SQLModel definitions for unified threads, messages, and outbound queue.
"""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlmodel import SQLModel, Field, Column, JSON


class UnifiedThread(SQLModel, table=True):
    __tablename__ = "et_threads"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="et_tenants.id", index=True)
    lead_id: int = Field(foreign_key="et_leads.id", index=True)
    agent_id: Optional[int] = Field(default=None, foreign_key="zairag_agents.id", index=True)
    channel: str = Field(max_length=32, index=True)
    status: str = Field(default="active", max_length=32, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UnifiedMessage(SQLModel, table=True):
    __tablename__ = "et_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="et_tenants.id", index=True)
    lead_id: int = Field(foreign_key="et_leads.id", index=True)
    thread_id: Optional[int] = Field(default=None, foreign_key="et_threads.id", index=True)
    channel_session_id: Optional[int] = Field(default=None, foreign_key="et_channel_sessions.id", index=True)

    channel: str = Field(max_length=32, index=True)
    external_message_id: str = Field(max_length=255, index=True)
    direction: str = Field(max_length=16, index=True)  # inbound | outbound
    message_type: str = Field(default="text", max_length=32)

    text_content: Optional[str] = None
    media_url: Optional[str] = None
    llm_provider: Optional[str] = Field(default=None, max_length=32, index=True)
    llm_model: Optional[str] = Field(default=None, max_length=128, index=True)
    llm_prompt_tokens: Optional[int] = Field(default=None, index=True)
    llm_completion_tokens: Optional[int] = Field(default=None, index=True)
    llm_total_tokens: Optional[int] = Field(default=None, index=True)
    llm_estimated_cost_usd: Optional[float] = Field(default=None, index=True)
    raw_payload: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    delivery_status: str = Field(default="received", max_length=32, index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class OutboundQueue(SQLModel, table=True):
    __tablename__ = "et_outbound_queue"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="et_tenants.id", index=True)
    message_id: int = Field(foreign_key="et_messages.id", index=True, unique=True)
    channel: str = Field(max_length=32, index=True)
    channel_session_id: Optional[int] = Field(default=None, foreign_key="et_channel_sessions.id", index=True)

    status: str = Field(default="queued", max_length=32, index=True)
    retry_count: int = Field(default=0)
    next_attempt_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    last_error: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ThreadInsight(SQLModel, table=True):
    __tablename__ = "et_thread_insights"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="et_tenants.id", index=True)
    thread_id: int = Field(foreign_key="et_threads.id", index=True, unique=True)
    lead_id: int = Field(foreign_key="et_leads.id", index=True)

    label: Optional[str] = Field(default=None, max_length=64)
    next_step: Optional[str] = Field(default=None, max_length=64)
    next_followup_at: Optional[datetime] = Field(default=None, index=True)
    summary: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
