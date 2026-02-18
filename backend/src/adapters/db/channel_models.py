"""
MODULE: Database Models - Multi-Channel Messaging
PURPOSE: SQLModel definitions for Channel Sessions and unified messaging schema.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from sqlmodel import Field, Relationship, SQLModel, Column, JSON
from sqlalchemy import UniqueConstraint

class ChannelType(str, Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    DISCORD = "discord"
    TELEGRAM = "telegram"

class SessionStatus(str, Enum):
    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    SUSPENDED = "suspended"

class MessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    REACTION = "reaction"
    DELETED = "deleted"

class ChannelSession(SQLModel, table=True):
    """
    Stores connection metadata for each messaging channel (WhatsApp, Email, Discord, Telegram).
    One tenant can have multiple channel sessions.
    """
    __tablename__ = "et_channel_sessions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "channel_type", "session_identifier", 
                        name="uq_channel_session"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="et_tenants.id", index=True)
    channel_type: ChannelType = Field(index=True)
    session_identifier: str = Field(max_length=255)  # Phone number, email, bot ID
    display_name: Optional[str] = Field(default=None, max_length=255)
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, index=True)
    session_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON),
    )  # Channel-specific config
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    threads: List["ConversationThread"] = Relationship(back_populates="channel_session")

# NOTE: ConversationThread is extended in crm_models.py to include channel_session_id
# NOTE: ChatMessageNew is extended in crm_models.py to include channel-specific fields
