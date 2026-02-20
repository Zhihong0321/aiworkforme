"""
MODULE: Database Models - User & Identity
PURPOSE: SQLModel definitions for Users, Roles, and Memberships.
"""
import importlib
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel, Column, JSON
from sqlalchemy import UniqueConstraint

Role = importlib.import_module("src.domain.entities.enums").Role

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

# To avoid circular imports, Tenant will be in tenant_models.py
# Reference strings are used for Relationship targets
