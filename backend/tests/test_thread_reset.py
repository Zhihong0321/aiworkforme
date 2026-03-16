from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from routers import agents
from routers.ai_crm_routes import list_ai_crm_threads
from routers.messaging_core_routes import reset_thread
from src.adapters.api.dependencies import AuthContext
from src.adapters.db.crm_models import AICRMThreadState, Lead
from src.adapters.db.messaging_models import OutboundQueue, UnifiedMessage, UnifiedThread
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
    session.add(Tenant(id=1, name="Tenant A"))
    session.commit()
    return session


def _auth_context() -> AuthContext:
    return AuthContext(
        user=User(id=10, email="tenant-user@test.local", password_hash="x", is_active=True),
        tenant=Tenant(id=1, name="Tenant A"),
        tenant_role=Role.TENANT_USER,
        is_platform_admin=False,
    )


def test_reset_thread_archives_old_thread_and_creates_fresh_active_thread():
    session = _make_session()
    auth = _auth_context()
    now = datetime.utcnow()

    created_agent = agents.create_agent(
        agents.AgentCreate(name="Reset Agent", system_prompt="Helpful"),
        session=session,
        auth=auth,
    )

    lead = Lead(
        tenant_id=1,
        external_id="+15550001111",
        name="Lead A",
        agent_id=int(created_agent.id),
        next_followup_at=now + timedelta(hours=4),
    )
    session.add(lead)
    session.commit()
    session.refresh(lead)

    thread = UnifiedThread(
        tenant_id=1,
        lead_id=int(lead.id),
        agent_id=int(created_agent.id),
        channel="whatsapp",
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(thread)
    session.commit()
    session.refresh(thread)

    outbound = UnifiedMessage(
        tenant_id=1,
        lead_id=int(lead.id),
        thread_id=int(thread.id),
        channel="whatsapp",
        external_message_id="out_reset_1",
        direction="outbound",
        message_type="text",
        text_content="queued follow-up",
        delivery_status="queued",
        created_at=now,
        updated_at=now,
    )
    session.add(outbound)
    session.commit()
    session.refresh(outbound)

    queue = OutboundQueue(
        tenant_id=1,
        message_id=int(outbound.id),
        channel="whatsapp",
        status="queued",
        retry_count=0,
        next_attempt_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(queue)

    state = AICRMThreadState(
        tenant_id=1,
        workspace_id=None,
        agent_id=int(created_agent.id),
        thread_id=int(thread.id),
        lead_id=int(lead.id),
        next_followup_at=now + timedelta(hours=4),
        reason_trace={"source": "test"},
        created_at=now,
        updated_at=now,
    )
    session.add(state)
    session.commit()

    result = reset_thread(
        thread_id=int(thread.id),
        session=session,
        auth=auth,
    )

    old_thread = session.get(UnifiedThread, int(thread.id))
    new_thread = session.get(UnifiedThread, int(result.new_thread_id))
    refreshed_queue = session.get(OutboundQueue, int(queue.id))
    refreshed_message = session.get(UnifiedMessage, int(outbound.id))
    refreshed_state = session.get(AICRMThreadState, int(state.id))
    refreshed_lead = session.get(Lead, int(lead.id))

    assert result.old_thread_id == int(thread.id)
    assert result.new_thread_id != int(thread.id)
    assert result.lead_id == int(lead.id)
    assert old_thread is not None
    assert old_thread.status == "archived"
    assert new_thread is not None
    assert new_thread.status == "active"
    assert new_thread.lead_id == int(lead.id)
    assert new_thread.agent_id == int(created_agent.id)
    assert new_thread.channel == "whatsapp"
    assert refreshed_queue is not None
    assert refreshed_queue.status == "cancelled"
    assert refreshed_message is not None
    assert refreshed_message.delivery_status == "cancelled"
    assert refreshed_state is not None
    assert refreshed_state.next_followup_at is None
    assert refreshed_lead is not None
    assert refreshed_lead.next_followup_at is None

    rows = list_ai_crm_threads(
        agent_id=int(created_agent.id),
        session=session,
        auth=auth,
    )
    assert len(rows) == 1
    assert rows[0].thread_id == int(new_thread.id)
