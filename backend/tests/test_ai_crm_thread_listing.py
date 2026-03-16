from __future__ import annotations

from datetime import datetime

from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from routers.ai_crm_routes import list_ai_crm_threads
from src.adapters.api.dependencies import AuthContext
from src.adapters.db.agent_models import Agent
from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.messaging_models import UnifiedMessage, UnifiedThread
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


def test_list_ai_crm_threads_repairs_legacy_thread_owner_from_latest_channel_message():
    session = _make_session()
    auth = _auth_context()
    now = datetime.utcnow()

    channel_a = ChannelSession(
        id=11,
        tenant_id=1,
        channel_type=ChannelType.WHATSAPP,
        session_identifier="601121000011",
        display_name="Channel A",
        status=SessionStatus.ACTIVE,
        session_metadata={},
    )
    channel_b = ChannelSession(
        id=12,
        tenant_id=1,
        channel_type=ChannelType.WHATSAPP,
        session_identifier="601121000012",
        display_name="Channel B",
        status=SessionStatus.ACTIVE,
        session_metadata={},
    )
    agent_a = Agent(
        id=101,
        tenant_id=1,
        name="Agent A",
        system_prompt="Prompt A",
        preferred_channel_session_id=channel_a.id,
    )
    agent_b = Agent(
        id=102,
        tenant_id=1,
        name="Agent B",
        system_prompt="Prompt B",
        preferred_channel_session_id=channel_b.id,
    )
    workspace = Workspace(id=201, tenant_id=1, name="Main")
    lead = Lead(
        id=301,
        tenant_id=1,
        workspace_id=workspace.id,
        agent_id=None,
        external_id="601199999999",
        name="Legacy Lead",
    )
    thread = UnifiedThread(
        id=401,
        tenant_id=1,
        lead_id=lead.id,
        agent_id=agent_a.id,
        channel="whatsapp",
        status="active",
        created_at=now,
        updated_at=now,
    )
    inbound = UnifiedMessage(
        id=501,
        tenant_id=1,
        lead_id=lead.id,
        thread_id=thread.id,
        channel_session_id=channel_b.id,
        channel="whatsapp",
        external_message_id="legacy_inbound_1",
        direction="inbound",
        message_type="text",
        text_content="Hello from the Channel B conversation.",
        delivery_status="received",
        created_at=now,
        updated_at=now,
    )
    session.add(channel_a)
    session.add(channel_b)
    session.add(agent_a)
    session.add(agent_b)
    session.add(workspace)
    session.add(lead)
    session.add(thread)
    session.add(inbound)
    session.commit()

    rows_for_agent_b = list_ai_crm_threads(
        agent_id=agent_b.id,
        session=session,
        auth=auth,
    )
    rows_for_agent_a = list_ai_crm_threads(
        agent_id=agent_a.id,
        session=session,
        auth=auth,
    )

    session.refresh(lead)
    session.refresh(thread)

    assert [row.thread_id for row in rows_for_agent_b] == [thread.id]
    assert rows_for_agent_a == []
    assert lead.agent_id == agent_b.id
    assert thread.agent_id == agent_b.id
