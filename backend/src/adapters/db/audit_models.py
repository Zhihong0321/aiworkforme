"""
MODULE: Database Models - Audit & Security
PURPOSE: SQLModel definitions for Audit Logs and Security Events.
"""
from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, Column, JSON

class AdminAuditLog(SQLModel, table=True):
    __tablename__ = "et_admin_audit_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: int = Field(foreign_key="et_users.id", index=True)
    tenant_id: Optional[int] = Field(default=None, index=True)
    action: str = Field(index=True)
    target_type: str
    target_id: Optional[str] = None
    details: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

class SecurityEventLog(SQLModel, table=True):
    __tablename__ = "et_security_events"
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: Optional[int] = Field(default=None, foreign_key="et_users.id", index=True)
    tenant_id: Optional[int] = Field(default=None, index=True)
    event_type: str = Field(index=True)
    endpoint: str
    method: str
    status_code: int = Field(index=True)
    reason: str = Field(index=True)
    details: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
