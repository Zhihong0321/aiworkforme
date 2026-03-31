from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from routers import calendar
from src.adapters.api.dependencies import AuthContext
from src.adapters.db.agent_models import Agent
from src.adapters.db.calendar_models import CalendarActionLog, CalendarConfig, CalendarDebugTrace, CalendarEvent
from src.adapters.db.channel_models import ChannelSession  # noqa: F401
from src.adapters.db.chat_models import ChatMessage, ChatSession  # noqa: F401
from src.adapters.db.crm_models import Lead, Workspace  # noqa: F401
from src.adapters.db.mcp_models import MCPServer  # noqa: F401
from src.adapters.db.messaging_models import OutboundQueue, ThreadInsight, UnifiedMessage, UnifiedThread  # noqa: F401
from src.adapters.db.tenant_models import Tenant
from src.adapters.db.user_models import User
from src.domain.entities.enums import Role


def _make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_calendar_debug_snapshot_shows_owner_calendar_and_runtime_traces():
    session = _make_session()
    tenant = Tenant(id=1, name="Tenant A")
    auth_user = User(id=10, email="viewer@test.local", password_hash="x", is_active=True)
    owner_user = User(id=11, email="owner@test.local", password_hash="x", is_active=True)
    agent = Agent(
        id=100,
        tenant_id=1,
        name="Sales Agent",
        system_prompt="Helpful.",
        calendar_enabled=True,
        calendar_owner_user_id=11,
    )
    workspace = Workspace(id=50, tenant_id=1, name="Default", agent_id=100)
    lead = Lead(id=70, tenant_id=1, workspace_id=50, external_id="601121000099", name="Test Lead", agent_id=100)
    thread = UnifiedThread(id=80, tenant_id=1, lead_id=70, agent_id=100, channel="whatsapp")
    inbound = UnifiedMessage(
        id=90,
        tenant_id=1,
        lead_id=70,
        thread_id=80,
        channel="whatsapp",
        external_message_id="in_1",
        direction="inbound",
        text_content="can we set an appointment tmr 2pm?",
        raw_payload={},
    )
    action_log = CalendarActionLog(
        tenant_id=1,
        agent_id=100,
        user_id=11,
        lead_id=70,
        event_id=120,
        tool_name="create_pending_appointment",
        action="create_pending",
        request_payload={"region": "Johor"},
        result_payload={"status": "pending"},
        result_status="pending",
    )
    trace = CalendarDebugTrace(
        tenant_id=1,
        agent_id=100,
        lead_id=70,
        thread_id=80,
        inbound_message_id=90,
        stage="runtime_calendar_tool_called",
        status="info",
        message="Calling calendar tool.",
        details={"tool_name": "create_pending_appointment"},
    )
    auth_user_event = CalendarEvent(
        id=110,
        tenant_id=1,
        user_id=10,
        lead_id=70,
        agent_id=100,
        title="Viewer Event",
        start_time=datetime.fromisoformat("2026-04-01T10:00:00"),
        end_time=datetime.fromisoformat("2026-04-01T10:30:00"),
        status="confirmed",
        source="manual",
    )
    owner_event = CalendarEvent(
        id=120,
        tenant_id=1,
        user_id=11,
        lead_id=70,
        agent_id=100,
        title="Pending Appointment",
        start_time=datetime.fromisoformat("2026-04-01T14:00:00"),
        end_time=datetime.fromisoformat("2026-04-01T14:30:00"),
        status="pending",
        source="ai_agent",
        pending_reason="details_unconfirmed",
    )
    config = CalendarConfig(tenant_id=1, user_id=11)
    session.add(tenant)
    session.add(auth_user)
    session.add(owner_user)
    session.add(agent)
    session.add(workspace)
    session.add(lead)
    session.add(thread)
    session.add(inbound)
    session.add(config)
    session.add(action_log)
    session.add(trace)
    session.add(auth_user_event)
    session.add(owner_event)
    session.commit()

    auth = AuthContext(
        user=auth_user,
        tenant=tenant,
        tenant_role=Role.TENANT_ADMIN,
        is_platform_admin=False,
    )

    result = calendar.calendar_debug_snapshot(
        agent_id=100,
        lead_id=70,
        thread_id=80,
        inbound_message_id=90,
        limit=20,
        session=session,
        auth=auth,
    )

    assert result["scope"]["calendar_owner_user_id"] == 11
    assert result["summary"]["trace_count"] == 1
    assert result["summary"]["action_log_count"] == 1
    assert result["summary"]["auth_user_event_count"] == 1
    assert result["summary"]["owner_user_event_count"] == 1
    assert result["traces"][0]["stage"] == "runtime_calendar_tool_called"
    assert result["action_logs"][0]["tool_name"] == "create_pending_appointment"
    assert result["owner_user_events"][0]["status"] == "pending"
    assert result["recent_messages"][0]["text_preview"].startswith("can we set an appointment")
