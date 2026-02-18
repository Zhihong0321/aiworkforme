from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from src.infra.database import get_session
from src.adapters.api.dependencies import require_tenant_access, AuthContext
from src.adapters.db.calendar_models import CalendarConfig, CalendarEvent

router = APIRouter(prefix="/api/v1/calendar", tags=["Calendar Management"])

@router.get("/config", response_model=CalendarConfig)
def get_calendar_config(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    config = session.exec(
        select(CalendarConfig).where(
            CalendarConfig.user_id == auth.user.id,
            CalendarConfig.tenant_id == auth.tenant.id
        )
    ).first()
    
    if not config:
        # Create default config if not exists
        config = CalendarConfig(
            user_id=auth.user.id,
            tenant_id=auth.tenant.id,
            meeting_types=[{"name": "Discovery Call", "duration_minutes": 30}],
            available_regions=["Online", "Office"],
            timezone="UTC"
        )
        session.add(config)
        session.commit()
        session.refresh(config)
    
    return config

@router.post("/config", response_model=CalendarConfig)
def update_calendar_config(
    payload: Dict[str, Any],
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    config = session.exec(
        select(CalendarConfig).where(
            CalendarConfig.user_id == auth.user.id,
            CalendarConfig.tenant_id == auth.tenant.id
        )
    ).first()
    
    if not config:
        config = CalendarConfig(user_id=auth.user.id, tenant_id=auth.tenant.id)
    
    if "meeting_types" in payload:
        config.meeting_types = payload["meeting_types"]
    if "available_regions" in payload:
        config.available_regions = payload["available_regions"]
    if "timezone" in payload:
        config.timezone = payload["timezone"]
    
    config.updated_at = datetime.utcnow()
    
    session.add(config)
    session.commit()
    session.refresh(config)
    return config

@router.get("/events", response_model=List[CalendarEvent])
def list_calendar_events(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    query = select(CalendarEvent).where(
        CalendarEvent.user_id == auth.user.id,
        CalendarEvent.tenant_id == auth.tenant.id
    )
    if start:
        query = query.where(CalendarEvent.end_time >= start)
    if end:
        query = query.where(CalendarEvent.start_time <= end)
    
    query = query.order_by(CalendarEvent.start_time.asc())
    
    return session.exec(query).all()

@router.post("/events", response_model=CalendarEvent)
def create_calendar_event(
    event_data: Dict[str, Any],
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    # Using Dict for flexible input validation or expansion
    event = CalendarEvent(
        user_id=auth.user.id,
        tenant_id=auth.tenant.id,
        lead_id=event_data.get("lead_id"),
        title=event_data.get("title", "New Event"),
        description=event_data.get("description"),
        start_time=datetime.fromisoformat(event_data["start_time"].replace("Z", "+00:00")),
        end_time=datetime.fromisoformat(event_data["end_time"].replace("Z", "+00:00")),
        event_type=event_data.get("event_type", "appointment"),
        meeting_type_name=event_data.get("meeting_type_name"),
        region=event_data.get("region"),
        status=event_data.get("status", "confirmed")
    )
    
    session.add(event)
    session.commit()
    session.refresh(event)
    return event

@router.delete("/events/{event_id}")
def delete_calendar_event(
    event_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    event = session.get(CalendarEvent, event_id)
    if not event or event.user_id != auth.user.id:
        raise HTTPException(status_code=404, detail="Event not found")
    
    session.delete(event)
    session.commit()
    return {"message": "Event deleted"}

@router.get("/availability")
def get_availability(
    date: datetime,
    duration_minutes: int = 30,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    """
    Check availability for a specific date.
    Returns list of free slots (tuples of start/end).
    Simplistic implementation: assume 9 AM - 6 PM working hours.
    """
    # Define working hours (e.g. 9:00 to 18:00)
    # Note: In a real app, this should come from user config.
    day_start = date.replace(hour=9, minute=0, second=0, microsecond=0)
    day_end = date.replace(hour=18, minute=0, second=0, microsecond=0)
    
    # Get all events for that day
    events = session.exec(
        select(CalendarEvent).where(
            CalendarEvent.user_id == auth.user.id,
            CalendarEvent.tenant_id == auth.tenant.id,
            CalendarEvent.start_time < day_end,
            CalendarEvent.end_time > day_start,
            CalendarEvent.status != "cancelled"
        ).order_by(CalendarEvent.start_time.asc())
    ).all()
    
    # Simple slot finding algorithm
    free_slots = []
    current_time = day_start
    
    for event in events:
        if event.start_time > current_time:
            gap = (event.start_time - current_time).total_seconds() / 60
            if gap >= duration_minutes:
                free_slots.append({
                    "start": current_time.isoformat(),
                    "end": event.start_time.isoformat()
                })
        current_time = max(current_time, event.end_time)
        
    if current_time < day_end:
        gap = (day_end - current_time).total_seconds() / 60
        if gap >= duration_minutes:
            free_slots.append({
                "start": current_time.isoformat(),
                "end": day_end.isoformat()
            })
            
    return {"date": date.isoformat(), "slots": free_slots}
