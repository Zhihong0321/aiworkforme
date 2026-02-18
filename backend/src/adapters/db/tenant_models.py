"""
MODULE: Database Models - Tenant
PURPOSE: SQLModel definitions for Tenants and System Settings.
"""
from typing import List, Optional
from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel

from src.domain.entities.enums import TenantStatus

class Tenant(SQLModel, table=True):
    __tablename__ = "et_tenants"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    status: TenantStatus = Field(default=TenantStatus.ACTIVE)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    memberships: List["TenantMembership"] = Relationship(back_populates="tenant")

class SystemSetting(SQLModel, table=True):
    __tablename__ = "zairag_system_settings"
    key: str = Field(primary_key=True)
    value: str
