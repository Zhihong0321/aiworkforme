import os
import json
import logging
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine, text

# Configure logging to stderr for MCP communication
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("calendar_mcp")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app_test.db")
engine = create_engine(DATABASE_URL)

# Initialize FastMCP
app = FastMCP("calendar_management")

@app.tool()
async def get_user_availability(user_id: int, tenant_id: int, date_str: str) -> str:
    """
    Checks the user's available slots for a given date (YYYY-MM-DD).
    Returns a list of free time slots.
    """
    try:
        # Simplistic 9-6 working hours
        date = datetime.fromisoformat(date_str.split('T')[0])
        day_start = date.replace(hour=9, minute=0, second=0)
        day_end = date.replace(hour=18, minute=0, second=0)
        
        with engine.connect() as conn:
            sql = """
                SELECT start_time, end_time 
                FROM et_calendar_events 
                WHERE user_id = :uid AND tenant_id = :tid 
                AND start_time < :end AND end_time > :start
                AND status != 'cancelled'
                ORDER BY start_time ASC
            """
            result = conn.execute(text(sql), {
                "uid": user_id, 
                "tid": tenant_id, 
                "start": day_start, 
                "end": day_end
            })
            events = [dict(row._mapping) for row in result]
            
        # Parse events and find gaps
        free_slots = []
        current_time = day_start
        
        for event in events:
            # Handle possible string/datetime from different DB backends
            e_start = event['start_time']
            if isinstance(e_start, str): e_start = datetime.fromisoformat(e_start.replace('Z', '+00:00')).replace(tzinfo=None)
            
            e_end = event['end_time']
            if isinstance(e_end, str): e_end = datetime.fromisoformat(e_end.replace('Z', '+00:00')).replace(tzinfo=None)

            if e_start > current_time:
                free_slots.append(f"{current_time.strftime('%H:%M')} - {e_start.strftime('%H:%M')}")
            current_time = max(current_time, e_end)
            
        if current_time < day_end:
            free_slots.append(f"{current_time.strftime('%H:%M')} - {day_end.strftime('%H:%M')}")
            
        if not free_slots:
            return f"No availability found for {date_str}."
            
        return f"Available slots for {date_str}:\n" + "\n".join([f"- {s}" for s in free_slots])
        
    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        return f"Error: {str(e)}"

@app.tool()
async def book_appointment(user_id: int, tenant_id: int, title: str, start_time: str, end_time: str, description: Optional[str] = None) -> str:
    """
    Books an appointment on behalf of the user.
    start_time and end_time should be in ISO format.
    """
    try:
        with engine.connect() as conn:
            # Check for overlaps
            check_sql = """
                SELECT id FROM et_calendar_events 
                WHERE user_id = :uid AND tenant_id = :tid
                AND start_time < :end AND end_time > :start
                AND status != 'cancelled'
            """
            overlap = conn.execute(text(check_sql), {
                "uid": user_id,
                "tid": tenant_id,
                "start": datetime.fromisoformat(start_time.replace('Z', '+00:00')),
                "end": datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            }).first()
            
            if overlap:
                return "Error: This time slot overlaps with an existing appointment."
            
            insert_sql = """
                INSERT INTO et_calendar_events (user_id, tenant_id, title, start_time, end_time, description, event_type, status, created_at, updated_at)
                VALUES (:uid, :tid, :title, :start, :end, :desc, 'appointment', 'confirmed', :now, :now)
            """
            now = datetime.utcnow()
            conn.execute(text(insert_sql), {
                "uid": user_id,
                "tid": tenant_id,
                "title": title,
                "start": datetime.fromisoformat(start_time.replace('Z', '+00:00')),
                "end": datetime.fromisoformat(end_time.replace('Z', '+00:00')),
                "desc": description,
                "now": now
            })
            conn.commit()
            
        return f"Successfully booked appointment: {title} from {start_time} to {end_time}"
    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        return f"Error: {str(e)}"

if __name__ == "__main__":
    app.run()
