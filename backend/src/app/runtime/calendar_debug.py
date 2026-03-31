from __future__ import annotations

from typing import Any, Dict, Optional

from sqlmodel import Session

from src.adapters.db.calendar_models import CalendarDebugTrace


def record_calendar_debug(
    session: Session,
    *,
    tenant_id: Optional[int],
    stage: str,
    status: str = "info",
    message: Optional[str] = None,
    agent_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    thread_id: Optional[int] = None,
    inbound_message_id: Optional[int] = None,
    outbound_message_id: Optional[int] = None,
    event_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Optional[CalendarDebugTrace]:
    if tenant_id is None:
        return None

    trace = CalendarDebugTrace(
        tenant_id=tenant_id,
        agent_id=agent_id,
        lead_id=lead_id,
        thread_id=thread_id,
        inbound_message_id=inbound_message_id,
        outbound_message_id=outbound_message_id,
        event_id=event_id,
        stage=str(stage or "").strip() or "unknown",
        status=str(status or "").strip() or "info",
        message=message,
        details=dict(details or {}),
    )
    session.add(trace)
    session.commit()
    session.refresh(trace)
    return trace
