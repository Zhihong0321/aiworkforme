from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime, time, timedelta
from typing import Any, Dict, Optional

from sqlmodel import Session, select

from src.adapters.db.agent_models import Agent
from src.adapters.db.calendar_models import CalendarActionLog, CalendarConfig, CalendarEvent


DEFAULT_WORKING_HOURS: Dict[str, Dict[str, str]] = {
    "monday": {"start": "09:00", "end": "18:00"},
    "tuesday": {"start": "09:00", "end": "18:00"},
    "wednesday": {"start": "09:00", "end": "18:00"},
    "thursday": {"start": "09:00", "end": "18:00"},
    "friday": {"start": "09:00", "end": "18:00"},
}


@dataclass
class CalendarActionResult:
    status: str
    event_id: Optional[int]
    message_for_ai: str
    reason: Optional[str] = None
    suggested_next_action: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "event_id": self.event_id,
            "message_for_ai": self.message_for_ai,
            "reason": self.reason,
            "suggested_next_action": self.suggested_next_action,
        }


def _parse_iso_datetime(value: Optional[Any]) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _normalize_working_hours(config: Optional[CalendarConfig]) -> Dict[str, Dict[str, str]]:
    raw = dict((config.working_hours or {})) if config else {}
    return raw or dict(DEFAULT_WORKING_HOURS)


def _day_window(config: Optional[CalendarConfig], for_date: date_cls) -> tuple[datetime, datetime]:
    working_hours = _normalize_working_hours(config)
    weekday_name = for_date.strftime("%A").lower()
    day_config = working_hours.get(weekday_name) or {}
    start_raw = str(day_config.get("start") or "09:00")
    end_raw = str(day_config.get("end") or "18:00")
    start_hour, start_minute = [int(part) for part in start_raw.split(":", 1)]
    end_hour, end_minute = [int(part) for part in end_raw.split(":", 1)]
    return (
        datetime.combine(for_date, time(hour=start_hour, minute=start_minute)),
        datetime.combine(for_date, time(hour=end_hour, minute=end_minute)),
    )


def _duration_for_request(
    config: Optional[CalendarConfig],
    meeting_type_name: Optional[str],
    duration_minutes: Optional[int],
) -> int:
    if duration_minutes is not None:
        return max(1, int(duration_minutes))
    if config and meeting_type_name:
        normalized = str(meeting_type_name).strip().lower()
        for item in list(config.meeting_types or []):
            if str(item.get("name") or "").strip().lower() == normalized:
                try:
                    return max(
                        1,
                        int(item.get("duration_minutes") or config.default_meeting_duration_minutes or 30),
                    )
                except Exception:
                    break
    return max(1, int(config.default_meeting_duration_minutes if config else 30))


def _validate_meeting_type(agent: Agent, config: Optional[CalendarConfig], meeting_type_name: Optional[str]) -> Optional[str]:
    if not bool(agent.calendar_require_meeting_type_validation):
        return None
    if not str(meeting_type_name or "").strip():
        return "meeting_type_required"
    if not config or not list(config.meeting_types or []):
        return "meeting_type_config_missing"
    normalized = str(meeting_type_name).strip().lower()
    for item in list(config.meeting_types or []):
        if str(item.get("name") or "").strip().lower() == normalized:
            return None
    return "meeting_type_not_allowed"


def _validate_region(
    agent: Agent,
    config: Optional[CalendarConfig],
    region: Optional[str],
    meeting_type_name: Optional[str],
) -> Optional[str]:
    if not bool(agent.calendar_require_region_validation):
        return None

    region_text = str(region or "").strip()
    if not region_text:
        return "region_required"
    if not config:
        return "region_config_missing"

    normalized_region = region_text.lower()
    allowed_regions = [str(item).strip().lower() for item in list(config.available_regions or []) if str(item).strip()]
    if allowed_regions and normalized_region not in allowed_regions:
        return "region_not_allowed"

    if meeting_type_name:
        normalized_type = str(meeting_type_name).strip().lower()
        for item in list(config.meeting_types or []):
            if str(item.get("name") or "").strip().lower() != normalized_type:
                continue
            specific_regions = [
                str(value).strip().lower()
                for value in list(item.get("allowed_regions") or [])
                if str(value).strip()
            ]
            if specific_regions and normalized_region not in specific_regions:
                return "region_not_allowed_for_meeting_type"
            break

    return None


def _record_action(
    session: Session,
    *,
    tenant_id: Optional[int],
    agent_id: Optional[int],
    user_id: Optional[int],
    lead_id: Optional[int],
    event_id: Optional[int],
    tool_name: str,
    action: str,
    request_payload: Dict[str, Any],
    result: CalendarActionResult,
    error_message: Optional[str] = None,
) -> None:
    session.add(
        CalendarActionLog(
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            lead_id=lead_id,
            event_id=event_id,
            tool_name=tool_name,
            action=action,
            request_payload=request_payload,
            result_payload=result.as_dict(),
            result_status=result.status,
            error_message=error_message,
        )
    )
    session.commit()


def _create_event(
    session: Session,
    *,
    tenant_id: int,
    user_id: int,
    lead_id: Optional[int],
    agent_id: Optional[int],
    title: str,
    start_time: datetime,
    end_time: datetime,
    description: Optional[str],
    event_type: str,
    meeting_type_name: Optional[str],
    region: Optional[str],
    status: str,
    source: str,
    needs_human_followup: bool,
    pending_reason: Optional[str],
    customer_notes: Optional[str],
    requested_start_time: Optional[datetime],
    requested_end_time: Optional[datetime],
    resolution_notes: Optional[str],
) -> CalendarEvent:
    event = CalendarEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        lead_id=lead_id,
        agent_id=agent_id,
        title=title,
        description=description,
        start_time=start_time,
        end_time=end_time,
        event_type=event_type,
        meeting_type_name=meeting_type_name,
        region=region,
        status=status,
        source=source,
        needs_human_followup=needs_human_followup,
        pending_reason=pending_reason,
        customer_notes=customer_notes,
        requested_start_time=requested_start_time,
        requested_end_time=requested_end_time,
        resolution_notes=resolution_notes,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def _find_overlapping_confirmed_event(
    session: Session,
    *,
    tenant_id: int,
    user_id: int,
    start_time: datetime,
    end_time: datetime,
) -> Optional[CalendarEvent]:
    return session.exec(
        select(CalendarEvent).where(
            CalendarEvent.tenant_id == tenant_id,
            CalendarEvent.user_id == user_id,
            CalendarEvent.status == "confirmed",
            CalendarEvent.start_time < end_time,
            CalendarEvent.end_time > start_time,
        )
    ).first()


def get_calendar_owner_for_agent(session: Session, tenant_id: int, agent_id: int) -> Optional[int]:
    agent = session.get(Agent, agent_id)
    if not agent or int(agent.tenant_id or 0) != int(tenant_id):
        return None
    owner_user_id = getattr(agent, "calendar_owner_user_id", None)
    return int(owner_user_id) if owner_user_id is not None else None


def get_calendar_capabilities(session: Session, tenant_id: int, agent_id: int) -> Dict[str, Any]:
    agent = session.get(Agent, agent_id)
    if not agent or int(agent.tenant_id or 0) != int(tenant_id):
        return {
            "calendar_enabled": False,
            "owner_user_id": None,
            "reason": "agent_not_found",
            "can_confirm": False,
        }

    owner_user_id = get_calendar_owner_for_agent(session, tenant_id, agent_id)
    config = None
    if owner_user_id is not None:
        config = session.exec(
            select(CalendarConfig).where(
                CalendarConfig.tenant_id == tenant_id,
                CalendarConfig.user_id == owner_user_id,
            )
        ).first()

    return {
        "calendar_enabled": bool(agent.calendar_enabled),
        "owner_user_id": owner_user_id,
        "timezone": config.timezone if config else "UTC",
        "meeting_types": list(config.meeting_types or []) if config else [],
        "available_regions": list(config.available_regions or []) if config else [],
        "working_hours": _normalize_working_hours(config),
        "buffer_minutes": int(config.buffer_minutes or 0) if config else 0,
        "advance_notice_minutes": int(config.advance_notice_minutes or 0) if config else 0,
        "default_meeting_duration_minutes": int(config.default_meeting_duration_minutes or 30) if config else 30,
        "can_confirm": bool(agent.calendar_enabled and owner_user_id is not None and config and config.calendar_enabled),
        "reason": None,
    }


def get_user_availability(
    session: Session,
    *,
    tenant_id: int,
    agent_id: int,
    date_value: datetime | date_cls,
    duration_minutes: Optional[int] = None,
    meeting_type_name: Optional[str] = None,
    region: Optional[str] = None,
) -> Dict[str, Any]:
    agent = session.get(Agent, agent_id)
    if not agent or int(agent.tenant_id or 0) != int(tenant_id):
        return {"status": "rejected", "reason": "agent_not_found", "slots": []}
    if not bool(agent.calendar_enabled):
        return {"status": "rejected", "reason": "calendar_disabled", "slots": []}

    owner_user_id = get_calendar_owner_for_agent(session, tenant_id, agent_id)
    if owner_user_id is None:
        return {"status": "rejected", "reason": "calendar_owner_missing", "slots": []}

    config = session.exec(
        select(CalendarConfig).where(
            CalendarConfig.tenant_id == tenant_id,
            CalendarConfig.user_id == owner_user_id,
        )
    ).first()
    if not config or not bool(config.calendar_enabled):
        return {"status": "rejected", "reason": "calendar_config_missing", "slots": []}

    meeting_type_error = _validate_meeting_type(agent, config, meeting_type_name)
    if meeting_type_error:
        return {"status": "rejected", "reason": meeting_type_error, "slots": []}
    region_error = _validate_region(agent, config, region, meeting_type_name)
    if region_error:
        return {"status": "rejected", "reason": region_error, "slots": []}

    for_date = date_value.date() if isinstance(date_value, datetime) else date_value
    day_start, day_end = _day_window(config, for_date)
    buffer_minutes = int(config.buffer_minutes or 0)
    slot_duration = _duration_for_request(config, meeting_type_name, duration_minutes)

    events = session.exec(
        select(CalendarEvent).where(
            CalendarEvent.tenant_id == tenant_id,
            CalendarEvent.user_id == owner_user_id,
            CalendarEvent.status == "confirmed",
            CalendarEvent.start_time < day_end,
            CalendarEvent.end_time > day_start,
        ).order_by(CalendarEvent.start_time.asc())
    ).all()

    slots = []
    current_time = day_start
    for event in events:
        busy_start = event.start_time - timedelta(minutes=buffer_minutes)
        busy_end = event.end_time + timedelta(minutes=buffer_minutes)
        if busy_start > current_time and (busy_start - current_time).total_seconds() >= slot_duration * 60:
            slots.append({"start": current_time.isoformat(), "end": busy_start.isoformat()})
        if busy_end > current_time:
            current_time = busy_end

    if current_time < day_end and (day_end - current_time).total_seconds() >= slot_duration * 60:
        slots.append({"start": current_time.isoformat(), "end": day_end.isoformat()})

    return {
        "status": "ok",
        "reason": None,
        "timezone": config.timezone,
        "owner_user_id": owner_user_id,
        "duration_minutes": slot_duration,
        "slots": slots,
    }


def create_pending_appointment(
    session: Session,
    *,
    tenant_id: int,
    agent_id: int,
    lead_id: Optional[int],
    title: str,
    requested_start_time: Optional[datetime | str] = None,
    requested_end_time: Optional[datetime | str] = None,
    meeting_type_name: Optional[str] = None,
    region: Optional[str] = None,
    description: Optional[str] = None,
    customer_notes: Optional[str] = None,
    pending_reason: Optional[str] = None,
    source: str = "ai_agent",
    log_action: bool = True,
) -> CalendarActionResult:
    agent = session.get(Agent, agent_id)
    request_payload = {
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "lead_id": lead_id,
        "title": title,
        "requested_start_time": str(requested_start_time) if requested_start_time is not None else None,
        "requested_end_time": str(requested_end_time) if requested_end_time is not None else None,
        "meeting_type_name": meeting_type_name,
        "region": region,
        "pending_reason": pending_reason,
    }

    if not agent or int(agent.tenant_id or 0) != int(tenant_id):
        result = CalendarActionResult(
            status="rejected",
            event_id=None,
            message_for_ai="I couldn't create a pending appointment because the agent could not be resolved.",
            reason="agent_not_found",
            suggested_next_action="handoff_to_tenant_user",
        )
        if log_action:
            _record_action(
                session,
                tenant_id=tenant_id,
                agent_id=agent_id,
                user_id=None,
                lead_id=lead_id,
                event_id=None,
                tool_name="create_pending_appointment",
                action="create_pending",
                request_payload=request_payload,
                result=result,
            )
        return result

    if not bool(agent.calendar_enabled):
        result = CalendarActionResult(
            status="rejected",
            event_id=None,
            message_for_ai="Calendar is disabled for this agent, so I can't create an appointment record.",
            reason="calendar_disabled",
            suggested_next_action="handoff_to_tenant_user",
        )
        if log_action:
            _record_action(
                session,
                tenant_id=tenant_id,
                agent_id=agent_id,
                user_id=getattr(agent, "calendar_owner_user_id", None),
                lead_id=lead_id,
                event_id=None,
                tool_name="create_pending_appointment",
                action="create_pending",
                request_payload=request_payload,
                result=result,
            )
        return result

    owner_user_id = get_calendar_owner_for_agent(session, tenant_id, agent_id)
    if owner_user_id is None:
        result = CalendarActionResult(
            status="rejected",
            event_id=None,
            message_for_ai="I couldn't create a pending appointment because no calendar owner is configured for this agent.",
            reason="calendar_owner_missing",
            suggested_next_action="handoff_to_tenant_user",
        )
        if log_action:
            _record_action(
                session,
                tenant_id=tenant_id,
                agent_id=agent_id,
                user_id=None,
                lead_id=lead_id,
                event_id=None,
                tool_name="create_pending_appointment",
                action="create_pending",
                request_payload=request_payload,
                result=result,
            )
        return result

    requested_start = _parse_iso_datetime(requested_start_time)
    requested_end = _parse_iso_datetime(requested_end_time)
    event = _create_event(
        session,
        tenant_id=tenant_id,
        user_id=owner_user_id,
        lead_id=lead_id,
        agent_id=agent_id,
        title=title,
        start_time=requested_start or datetime.utcnow(),
        end_time=requested_end or (requested_start or datetime.utcnow()) + timedelta(minutes=30),
        description=description,
        event_type="appointment",
        meeting_type_name=meeting_type_name,
        region=region,
        status="pending",
        source=source,
        needs_human_followup=True,
        pending_reason=pending_reason or "details_unconfirmed",
        customer_notes=customer_notes,
        requested_start_time=requested_start,
        requested_end_time=requested_end,
        resolution_notes=None,
    )
    result = CalendarActionResult(
        status="pending",
        event_id=event.id,
        message_for_ai="I created a pending appointment so the team can follow up directly with the customer.",
        reason=pending_reason or "details_unconfirmed",
        suggested_next_action="handoff_to_tenant_user",
    )
    if log_action:
        _record_action(
            session,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=owner_user_id,
            lead_id=lead_id,
            event_id=event.id,
            tool_name="create_pending_appointment",
            action="create_pending",
            request_payload=request_payload,
            result=result,
        )
    return result


def book_appointment(
    session: Session,
    *,
    tenant_id: int,
    agent_id: int,
    lead_id: Optional[int],
    title: str,
    start_time: Optional[datetime | str],
    end_time: Optional[datetime | str],
    meeting_type_name: Optional[str] = None,
    region: Optional[str] = None,
    description: Optional[str] = None,
    customer_notes: Optional[str] = None,
    source: str = "ai_agent",
) -> CalendarActionResult:
    agent = session.get(Agent, agent_id)
    request_payload = {
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "lead_id": lead_id,
        "title": title,
        "start_time": str(start_time) if start_time is not None else None,
        "end_time": str(end_time) if end_time is not None else None,
        "meeting_type_name": meeting_type_name,
        "region": region,
    }

    def _reject(message: str, reason: str, user_id: Optional[int]) -> CalendarActionResult:
        result = CalendarActionResult(
            status="rejected",
            event_id=None,
            message_for_ai=message,
            reason=reason,
            suggested_next_action="handoff_to_tenant_user",
        )
        _record_action(
            session,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            lead_id=lead_id,
            event_id=None,
            tool_name="book_appointment",
            action="book",
            request_payload=request_payload,
            result=result,
        )
        return result

    if not agent or int(agent.tenant_id or 0) != int(tenant_id):
        return _reject(
            "I couldn't book the appointment because the agent could not be resolved.",
            "agent_not_found",
            None,
        )
    if not bool(agent.calendar_enabled):
        return _reject(
            "Calendar is disabled for this agent, so I can't finalize a booking.",
            "calendar_disabled",
            getattr(agent, "calendar_owner_user_id", None),
        )

    owner_user_id = get_calendar_owner_for_agent(session, tenant_id, agent_id)
    if owner_user_id is None:
        return _reject(
            "I couldn't book the appointment because no calendar owner is configured for this agent.",
            "calendar_owner_missing",
            None,
        )

    config = session.exec(
        select(CalendarConfig).where(
            CalendarConfig.tenant_id == tenant_id,
            CalendarConfig.user_id == owner_user_id,
        )
    ).first()
    if not config or not bool(config.calendar_enabled):
        return _reject(
            "I couldn't book the appointment because the calendar configuration is incomplete.",
            "calendar_config_missing",
            owner_user_id,
        )

    parsed_start = _parse_iso_datetime(start_time)
    parsed_end = _parse_iso_datetime(end_time)

    if parsed_start is None or parsed_end is None or parsed_end <= parsed_start:
        result = create_pending_appointment(
            session,
            tenant_id=tenant_id,
            agent_id=agent_id,
            lead_id=lead_id,
            title=title,
            requested_start_time=parsed_start,
            requested_end_time=parsed_end,
            meeting_type_name=meeting_type_name,
            region=region,
            description=description,
            customer_notes=customer_notes,
            pending_reason="time_not_finalized",
            source=source,
            log_action=False,
        )
        _record_action(
            session,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=owner_user_id,
            lead_id=lead_id,
            event_id=result.event_id,
            tool_name="book_appointment",
            action="book",
            request_payload=request_payload,
            result=result,
        )
        return result

    meeting_type_error = _validate_meeting_type(agent, config, meeting_type_name)
    if meeting_type_error:
        result = create_pending_appointment(
            session,
            tenant_id=tenant_id,
            agent_id=agent_id,
            lead_id=lead_id,
            title=title,
            requested_start_time=parsed_start,
            requested_end_time=parsed_end,
            meeting_type_name=meeting_type_name,
            region=region,
            description=description,
            customer_notes=customer_notes,
            pending_reason=meeting_type_error,
            source=source,
            log_action=False,
        )
        _record_action(
            session,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=owner_user_id,
            lead_id=lead_id,
            event_id=result.event_id,
            tool_name="book_appointment",
            action="book",
            request_payload=request_payload,
            result=result,
        )
        return result

    region_error = _validate_region(agent, config, region, meeting_type_name)
    if region_error:
        result = create_pending_appointment(
            session,
            tenant_id=tenant_id,
            agent_id=agent_id,
            lead_id=lead_id,
            title=title,
            requested_start_time=parsed_start,
            requested_end_time=parsed_end,
            meeting_type_name=meeting_type_name,
            region=region,
            description=description,
            customer_notes=customer_notes,
            pending_reason=region_error,
            source=source,
            log_action=False,
        )
        _record_action(
            session,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=owner_user_id,
            lead_id=lead_id,
            event_id=result.event_id,
            tool_name="book_appointment",
            action="book",
            request_payload=request_payload,
            result=result,
        )
        return result

    overlap = _find_overlapping_confirmed_event(
        session,
        tenant_id=tenant_id,
        user_id=owner_user_id,
        start_time=parsed_start,
        end_time=parsed_end,
    )
    if overlap:
        result = create_pending_appointment(
            session,
            tenant_id=tenant_id,
            agent_id=agent_id,
            lead_id=lead_id,
            title=title,
            requested_start_time=parsed_start,
            requested_end_time=parsed_end,
            meeting_type_name=meeting_type_name,
            region=region,
            description=description,
            customer_notes=customer_notes,
            pending_reason="requested_time_unavailable",
            source=source,
            log_action=False,
        )
        _record_action(
            session,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=owner_user_id,
            lead_id=lead_id,
            event_id=result.event_id,
            tool_name="book_appointment",
            action="book",
            request_payload=request_payload,
            result=result,
        )
        return result

    event = _create_event(
        session,
        tenant_id=tenant_id,
        user_id=owner_user_id,
        lead_id=lead_id,
        agent_id=agent_id,
        title=title,
        start_time=parsed_start,
        end_time=parsed_end,
        description=description,
        event_type="appointment",
        meeting_type_name=meeting_type_name,
        region=region,
        status="confirmed",
        source=source,
        needs_human_followup=False,
        pending_reason=None,
        customer_notes=customer_notes,
        requested_start_time=parsed_start,
        requested_end_time=parsed_end,
        resolution_notes="Booked by calendar service.",
    )
    result = CalendarActionResult(
        status="confirmed",
        event_id=event.id,
        message_for_ai=f"Booked for {parsed_start.isoformat()} to {parsed_end.isoformat()}.",
        suggested_next_action="confirm_to_customer",
    )
    _record_action(
        session,
        tenant_id=tenant_id,
        agent_id=agent_id,
        user_id=owner_user_id,
        lead_id=lead_id,
        event_id=event.id,
        tool_name="book_appointment",
        action="book",
        request_payload=request_payload,
        result=result,
    )
    return result
