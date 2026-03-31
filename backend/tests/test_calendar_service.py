from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from src.adapters.db.agent_models import Agent
from src.adapters.db.calendar_models import CalendarActionLog, CalendarConfig, CalendarEvent
from src.adapters.db.channel_models import ChannelSession  # noqa: F401
from src.adapters.db.chat_models import ChatMessage, ChatSession  # noqa: F401
from src.adapters.db.crm_models import Lead, Workspace  # noqa: F401
from src.adapters.db.mcp_models import MCPServer  # noqa: F401
from src.adapters.db.messaging_models import OutboundQueue, ThreadInsight, UnifiedMessage, UnifiedThread  # noqa: F401
from src.adapters.db.tenant_models import Tenant
from src.adapters.db.user_models import User
from src.app.runtime.calendar_service import (
    book_appointment,
    create_pending_appointment,
    get_calendar_capabilities,
)


def _make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_foundation(session: Session) -> tuple[Tenant, User, Agent]:
    tenant = Tenant(id=1, name="Tenant A")
    owner = User(id=10, email="owner@test.local", password_hash="x", is_active=True)
    agent = Agent(
        id=100,
        tenant_id=1,
        name="Sales Agent",
        system_prompt="Helpful.",
        calendar_enabled=True,
        calendar_owner_user_id=10,
    )
    config = CalendarConfig(
        tenant_id=1,
        user_id=10,
        timezone="Asia/Shanghai",
        meeting_types=[{"name": "Discovery Call", "duration_minutes": 30, "allowed_regions": ["Online", "Office"]}],
        available_regions=["Online", "Office"],
        working_hours={
            "monday": {"start": "09:00", "end": "18:00"},
            "tuesday": {"start": "09:00", "end": "18:00"},
            "wednesday": {"start": "09:00", "end": "18:00"},
            "thursday": {"start": "09:00", "end": "18:00"},
            "friday": {"start": "09:00", "end": "18:00"},
        },
    )
    session.add(tenant)
    session.add(owner)
    session.add(agent)
    session.add(config)
    session.commit()
    return tenant, owner, agent


def test_get_calendar_capabilities_reports_owner_and_rules():
    session = _make_session()
    _seed_foundation(session)

    capabilities = get_calendar_capabilities(session, tenant_id=1, agent_id=100)

    assert capabilities["calendar_enabled"] is True
    assert capabilities["owner_user_id"] == 10
    assert capabilities["timezone"] == "Asia/Shanghai"
    assert capabilities["can_confirm"] is True
    assert capabilities["meeting_types"][0]["name"] == "Discovery Call"


def test_book_appointment_confirms_valid_slot_and_logs_action():
    session = _make_session()
    _seed_foundation(session)

    result = book_appointment(
        session,
        tenant_id=1,
        agent_id=100,
        lead_id=7,
        title="Discovery Call",
        start_time="2026-04-06T10:00:00",
        end_time="2026-04-06T10:30:00",
        meeting_type_name="Discovery Call",
        region="Online",
        description="Lead wants a discovery call.",
    )

    assert result.status == "confirmed"
    assert result.event_id is not None

    event = session.get(CalendarEvent, result.event_id)
    assert event is not None
    assert event.status == "confirmed"
    assert event.agent_id == 100
    assert event.user_id == 10
    assert event.region == "Online"

    log = session.exec(select(CalendarActionLog).where(CalendarActionLog.event_id == result.event_id)).first()
    assert log is not None
    assert log.result_status == "confirmed"
    assert log.tool_name == "book_appointment"


def test_book_appointment_creates_pending_when_time_overlaps():
    session = _make_session()
    _seed_foundation(session)
    session.add(
        CalendarEvent(
            tenant_id=1,
            user_id=10,
            agent_id=100,
            lead_id=5,
            title="Existing Meeting",
            start_time=datetime.fromisoformat("2026-04-06T10:00:00"),
            end_time=datetime.fromisoformat("2026-04-06T10:30:00"),
            status="confirmed",
            source="manual",
        )
    )
    session.commit()

    result = book_appointment(
        session,
        tenant_id=1,
        agent_id=100,
        lead_id=8,
        title="Discovery Call",
        start_time="2026-04-06T10:15:00",
        end_time="2026-04-06T10:45:00",
        meeting_type_name="Discovery Call",
        region="Online",
        description="Lead can meet, but slot is busy.",
    )

    assert result.status == "pending"
    assert result.reason == "requested_time_unavailable"

    event = session.get(CalendarEvent, result.event_id)
    assert event is not None
    assert event.status == "pending"
    assert event.needs_human_followup is True
    assert event.pending_reason == "requested_time_unavailable"


def test_create_pending_appointment_requires_enabled_agent_and_owner():
    session = _make_session()
    _seed_foundation(session)

    result = create_pending_appointment(
        session,
        tenant_id=1,
        agent_id=100,
        lead_id=9,
        title="Follow up with lead",
        requested_start_time="2026-04-06T11:00:00",
        meeting_type_name="Discovery Call",
        region="Office",
        pending_reason="time_not_finalized",
    )

    assert result.status == "pending"
    event = session.get(CalendarEvent, result.event_id)
    assert event is not None
    assert event.status == "pending"
    assert event.needs_human_followup is True
