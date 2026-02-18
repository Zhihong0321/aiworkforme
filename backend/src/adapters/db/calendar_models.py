"""
MODULE: Database Models - Calendar & Appointments
PURPOSE: SQLModel definitions for User Calendar Config and Events.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel, Column, JSON

class CalendarConfig(SQLModel, table=True):
    __tablename__ = "et_calendar_configs"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    user_id: int = Field(foreign_key="et_users.id", index=True)
    
    # Meeting types: [{"name": "Sales Call", "duration_minutes": 30, "description": "xxx"}, ...]
    meeting_types: List[Dict[str, Any]] = Field(default=[], sa_column=Column(JSON))
    
    # Available regions/locations: ["Singapore", "Kuala Lumpur", "Online"]
    available_regions: List[str] = Field(default=[], sa_column=Column(JSON))
    
    timezone: str = Field(default="UTC")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CalendarEvent(SQLModel, table=True):
    __tablename__ = "et_calendar_events"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    user_id: int = Field(foreign_key="et_users.id", index=True)
    lead_id: Optional[int] = Field(default=None, foreign_key="et_leads.id", index=True)
    
    title: str
    description: Optional[str] = None
    start_time: datetime = Field(index=True)
    end_time: datetime = Field(index=True)
    
    # 'appointment' or 'unavailable'
    event_type: str = Field(default="appointment", index=True) 
    
    meeting_type_name: Optional[str] = None # e.g. "Sales Call"
    region: Optional[str] = None
    
    # confirmed, pending, cancelled
    status: str = Field(default="confirmed", index=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
