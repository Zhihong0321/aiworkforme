import json
import logging
import sys
from datetime import datetime
from typing import Optional
from mcp.server.fastmcp import FastMCP
from sqlmodel import Session

from src.infra.database import engine
from src.app.runtime.calendar_service import (
    book_appointment as service_book_appointment,
    create_pending_appointment as service_create_pending_appointment,
    get_calendar_capabilities as service_get_calendar_capabilities,
    get_user_availability as service_get_user_availability,
)

# Configure logging to stderr for MCP communication
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("calendar_mcp")

# Initialize FastMCP
app = FastMCP("calendar_management")

@app.tool()
async def get_calendar_capabilities(tenant_id: int, agent_id: int) -> str:
    """
    Returns the calendar configuration available to the agent.
    """
    try:
        with Session(engine) as session:
            result = service_get_calendar_capabilities(session, tenant_id=tenant_id, agent_id=agent_id)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error getting calendar capabilities: {e}")
        return json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False)


@app.tool()
async def get_user_availability(
    tenant_id: int,
    agent_id: int,
    date_str: str,
    duration_minutes: Optional[int] = None,
    meeting_type_name: Optional[str] = None,
    region: Optional[str] = None,
) -> str:
    """
    Checks the calendar owner's available slots for a given date (YYYY-MM-DD).
    Returns a list of free time slots.
    """
    try:
        requested_date = datetime.fromisoformat(date_str.split("T")[0])
        with Session(engine) as session:
            result = service_get_user_availability(
                session,
                tenant_id=tenant_id,
                agent_id=agent_id,
                date_value=requested_date,
                duration_minutes=duration_minutes,
                meeting_type_name=meeting_type_name,
                region=region,
            )
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        return json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False)

@app.tool()
async def book_appointment(
    tenant_id: int,
    agent_id: int,
    title: str,
    start_time: Optional[str],
    end_time: Optional[str],
    lead_id: Optional[int] = None,
    meeting_type_name: Optional[str] = None,
    region: Optional[str] = None,
    description: Optional[str] = None,
    customer_notes: Optional[str] = None,
) -> str:
    """
    Books an appointment on behalf of the tenant through the agent's configured calendar owner.
    start_time and end_time should be in ISO format.
    """
    try:
        with Session(engine) as session:
            result = service_book_appointment(
                session,
                tenant_id=tenant_id,
                agent_id=agent_id,
                lead_id=lead_id,
                title=title,
                start_time=start_time,
                end_time=end_time,
                meeting_type_name=meeting_type_name,
                region=region,
                description=description,
                customer_notes=customer_notes,
            )
        return json.dumps(result.as_dict(), ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        return json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False)


@app.tool()
async def create_pending_appointment(
    tenant_id: int,
    agent_id: int,
    title: str,
    lead_id: Optional[int] = None,
    requested_start_time: Optional[str] = None,
    requested_end_time: Optional[str] = None,
    meeting_type_name: Optional[str] = None,
    region: Optional[str] = None,
    description: Optional[str] = None,
    customer_notes: Optional[str] = None,
    pending_reason: Optional[str] = None,
) -> str:
    """
    Creates a pending appointment when the customer wants to meet but the exact details are not finalized.
    """
    try:
        with Session(engine) as session:
            result = service_create_pending_appointment(
                session,
                tenant_id=tenant_id,
                agent_id=agent_id,
                lead_id=lead_id,
                title=title,
                requested_start_time=requested_start_time,
                requested_end_time=requested_end_time,
                meeting_type_name=meeting_type_name,
                region=region,
                description=description,
                customer_notes=customer_notes,
                pending_reason=pending_reason,
            )
        return json.dumps(result.as_dict(), ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error creating pending appointment: {e}")
        return json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False)

if __name__ == "__main__":
    app.run()
