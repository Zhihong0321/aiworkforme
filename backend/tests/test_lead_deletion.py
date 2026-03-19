from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from routers.leads import delete_lead
from src.adapters.api.dependencies import AuthContext
from src.adapters.db.agent_models import Agent
from src.adapters.db.calendar_models import CalendarEvent
from src.adapters.db.crm_models import (
    AICRMThreadState,
    ChatMessageNew,
    ConversationThread,
    Lead,
    LeadMemory,
    PolicyDecision,
    Workspace,
)
from src.adapters.db.messaging_models import OutboundQueue, ThreadInsight, UnifiedMessage, UnifiedThread
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
    session = Session(engine)
    session.exec(text("PRAGMA foreign_keys=ON"))
    session.add(Tenant(id=1, name="Tenant A"))
    session.commit()
    session.add(User(id=1, email="calendar-owner@test.local", password_hash="x", is_active=True))
    session.add(Agent(id=1, tenant_id=1, name="Delete Agent", system_prompt="Helpful"))
    session.commit()
    return session


def _auth_context() -> AuthContext:
    return AuthContext(
        user=User(id=10, email="tenant-user@test.local", password_hash="x", is_active=True),
        tenant=Tenant(id=1, name="Tenant A"),
        tenant_role=Role.TENANT_USER,
        is_platform_admin=False,
    )


def test_delete_lead_removes_contact_and_all_conversation_history():
    session = _make_session()
    auth = _auth_context()
    now = datetime.utcnow()

    workspace = Workspace(id=101, tenant_id=1, name="Main")
    lead = Lead(
        id=201,
        tenant_id=1,
        workspace_id=workspace.id,
        external_id="601155500001",
        name="Delete Me",
    )
    session.add(workspace)
    session.add(lead)
    session.commit()

    unified_thread = UnifiedThread(
        id=301,
        tenant_id=1,
        lead_id=lead.id,
        agent_id=None,
        channel="whatsapp",
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(unified_thread)
    session.commit()

    unified_message = UnifiedMessage(
        id=401,
        tenant_id=1,
        lead_id=lead.id,
        thread_id=unified_thread.id,
        channel="whatsapp",
        external_message_id="msg-delete-1",
        direction="outbound",
        message_type="text",
        text_content="hello",
        delivery_status="queued",
        created_at=now,
        updated_at=now,
    )
    session.add(unified_message)
    session.commit()

    queue = OutboundQueue(
        id=501,
        tenant_id=1,
        message_id=unified_message.id,
        channel="whatsapp",
        status="queued",
        retry_count=0,
        next_attempt_at=now,
        created_at=now,
        updated_at=now,
    )
    insight = ThreadInsight(
        id=601,
        tenant_id=1,
        thread_id=unified_thread.id,
        lead_id=lead.id,
        summary="summary",
        updated_at=now,
    )
    legacy_thread = ConversationThread(
        id=701,
        tenant_id=1,
        workspace_id=workspace.id,
        lead_id=lead.id,
        status="active",
        created_at=now,
    )
    session.add(queue)
    session.add(insight)
    session.add(legacy_thread)
    session.commit()

    legacy_message = ChatMessageNew(
        id=801,
        tenant_id=1,
        thread_id=legacy_thread.id,
        channel_message_id="legacy-msg-1",
        channel_timestamp=int(now.timestamp() * 1000),
        direction="inbound",
        message_type="text",
        role="user",
        content="old chat",
        created_at=now,
    )
    policy = PolicyDecision(
        id=901,
        tenant_id=1,
        workspace_id=workspace.id,
        lead_id=lead.id,
        allow_send=True,
        reason_code="ALLOW",
        rule_trace={},
        next_allowed_at=now + timedelta(hours=1),
        created_at=now,
    )
    memory = LeadMemory(
        id=1001,
        tenant_id=1,
        lead_id=lead.id,
        summary="remember this",
        facts=["fact-a"],
        last_updated_at=now,
    )
    state = AICRMThreadState(
        id=1101,
        tenant_id=1,
        workspace_id=workspace.id,
        agent_id=1,
        thread_id=unified_thread.id,
        lead_id=lead.id,
        reason_trace={"source": "test"},
        created_at=now,
        updated_at=now,
    )
    event = CalendarEvent(
        id=1201,
        tenant_id=1,
        user_id=1,
        lead_id=lead.id,
        title="Appointment",
        description="desc",
        start_time=now,
        end_time=now + timedelta(hours=1),
        created_at=now,
        updated_at=now,
    )
    session.add(legacy_message)
    session.add(policy)
    session.add(memory)
    session.add(state)
    session.add(event)
    session.commit()

    result = delete_lead(
        lead_id=lead.id,
        session=session,
        auth=auth,
    )

    assert result == {
        "status": "deleted",
        "lead_id": lead.id,
        "unified_messages": 1,
        "outbound_queue_rows": 1,
        "unified_threads": 1,
        "thread_insights": 1,
        "legacy_messages": 1,
        "legacy_threads": 1,
        "policy_decisions": 1,
        "lead_memories": 1,
        "ai_crm_thread_states": 1,
        "calendar_events": 1,
    }

    assert session.get(Lead, lead.id) is None
    assert session.exec(select(UnifiedThread).where(UnifiedThread.lead_id == lead.id)).all() == []
    assert session.exec(select(UnifiedMessage).where(UnifiedMessage.lead_id == lead.id)).all() == []
    assert session.exec(select(OutboundQueue).where(OutboundQueue.id == queue.id)).all() == []
    assert session.exec(select(ThreadInsight).where(ThreadInsight.id == insight.id)).all() == []
    assert session.exec(select(ConversationThread).where(ConversationThread.lead_id == lead.id)).all() == []
    assert session.exec(select(ChatMessageNew).where(ChatMessageNew.id == legacy_message.id)).all() == []
    assert session.exec(select(PolicyDecision).where(PolicyDecision.lead_id == lead.id)).all() == []
    assert session.exec(select(LeadMemory).where(LeadMemory.lead_id == lead.id)).all() == []
    assert session.exec(select(AICRMThreadState).where(AICRMThreadState.lead_id == lead.id)).all() == []
    assert session.exec(select(CalendarEvent).where(CalendarEvent.lead_id == lead.id)).all() == []
