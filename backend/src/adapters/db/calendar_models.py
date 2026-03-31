"""
MODULE: Database Models - Calendar & Appointments
PURPOSE: SQLModel definitions for User Calendar Config, Events, and audit records.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, Column, JSON

class CalendarConfig(SQLModel, table=True):
    __tablename__ = "et_calendar_configs"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    user_id: int = Field(foreign_key="et_users.id", index=True)
    
    # Meeting types: [{"name": "Sales Call", "duration_minutes": 30, "description": "xxx"}, ...]
    meeting_types: List[Dict[str, Any]] = Field(default=[], sa_column=Column(JSON))
    
    # Available regions/locations: ["Singapore", "Kuala Lumpur", "Online"]
    available_regions: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    working_hours: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    buffer_minutes: int = Field(default=0)
    advance_notice_minutes: int = Field(default=0)
    default_meeting_duration_minutes: int = Field(default=30)
    calendar_enabled: bool = Field(default=True)
    
    timezone: str = Field(default="UTC")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CalendarEvent(SQLModel, table=True):
    __tablename__ = "et_calendar_events"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    user_id: int = Field(foreign_key="et_users.id", index=True)
    lead_id: Optional[int] = Field(default=None, foreign_key="et_leads.id", index=True)
    agent_id: Optional[int] = Field(default=None, foreign_key="zairag_agents.id", index=True)
    
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
    source: str = Field(default="manual", index=True)
    needs_human_followup: bool = Field(default=False, index=True)
    pending_reason: Optional[str] = None
    customer_notes: Optional[str] = None
    requested_start_time: Optional[datetime] = Field(default=None, index=True)
    requested_end_time: Optional[datetime] = Field(default=None, index=True)
    resolution_notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CalendarActionLog(SQLModel, table=True):
    __tablename__ = "et_calendar_action_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="et_tenants.id", index=True)
    agent_id: Optional[int] = Field(default=None, foreign_key="zairag_agents.id", index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="et_users.id", index=True)
    lead_id: Optional[int] = Field(default=None, foreign_key="et_leads.id", index=True)
    event_id: Optional[int] = Field(default=None, foreign_key="et_calendar_events.id", index=True)
    tool_name: str = Field(index=True)
    action: str = Field(index=True)
    request_payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    result_payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    result_status: str = Field(index=True)
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
