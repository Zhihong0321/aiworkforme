from __future__ import annotations

from fastapi import HTTPException
import pytest
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from routers.ai_crm_routes import list_ai_crm_threads
from routers.messaging_core_routes import create_inbound_message
from routers.messaging_schemas import InboundCreateRequest
from src.adapters.api.dependencies import AuthContext
from src.adapters.db.agent_models import Agent
from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.messaging_models import UnifiedMessage, UnifiedThread
from src.adapters.db.tenant_models import Tenant
from src.adapters.db.user_models import User
from src.domain.entities.enums import Role


def _build_auth() -> AuthContext:
    return AuthContext(
        user=User(id=10, email="tenant-user@test.local", password_hash="x", is_active=True),
        tenant=Tenant(id=1, name="Tenant A"),
        tenant_role=Role.TENANT_USER,
        is_platform_admin=False,
    )


def _build_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    db = Session(engine)
    db.add(Tenant(id=1, name="Tenant A"))
    db.add(Agent(id=1, tenant_id=1, name="Agent", system_prompt="Prompt"))
    db.add(Workspace(id=1, tenant_id=1, name="Main", agent_id=1))
    db.add(
        ChannelSession(
            id=2,
            tenant_id=1,
            channel_type=ChannelType.WHATSAPP,
            session_identifier="601121000099",
            display_name="Primary WA",
            status=SessionStatus.ACTIVE,
            session_metadata={},
        )
    )
    db.commit()
    return db


def test_inbound_resolves_existing_lead_from_sender_phone():
    session = _build_session()
    auth = _build_auth()
    lead = Lead(tenant_id=1, workspace_id=1, external_id="601158942400", name="Lead A")
    session.add(lead)
    session.commit()
    session.refresh(lead)

    response = create_inbound_message(
        InboundCreateRequest(
            channel="whatsapp",
            external_message_id="msg_in_001",
            direction="inbound",
            sender_phone="601158942400",
            recipient_phone="601121000099",
            text_content="hello",
            channel_session_id=2,
        ),
        session=session,
        auth=auth,
    )

    saved = session.exec(select(UnifiedMessage).where(UnifiedMessage.id == response.message_id)).first()
    assert saved is not None
    assert saved.lead_id == lead.id
    assert saved.thread_id is not None


def test_inbound_falls_back_to_only_active_session_when_phone_cannot_map():
    session = _build_session()
    auth = _build_auth()

    response = create_inbound_message(
        InboundCreateRequest(
            channel="whatsapp",
            external_message_id="msg_in_002",
            direction="inbound",
            sender_phone="601199999999",
            recipient_phone="601188888888",
            text_content="hello",
        ),
        session=session,
        auth=auth,
    )

    saved = session.exec(select(UnifiedMessage).where(UnifiedMessage.id == response.message_id)).first()
    resolved_session = session.get(ChannelSession, 2)

    assert saved is not None
    assert saved.channel_session_id == 2
    assert resolved_session is not None
    assert resolved_session.display_name == "601188888888"


def test_inbound_assigns_thread_to_channel_owner_and_surfaces_in_ai_crm_inbox():
    session = _build_session()
    auth = _build_auth()

    channel_a = ChannelSession(
        id=3,
        tenant_id=1,
        channel_type=ChannelType.WHATSAPP,
        session_identifier="601121000098",
        display_name="Secondary WA",
        status=SessionStatus.ACTIVE,
        session_metadata={},
    )
    agent_b = Agent(
        id=2,
        tenant_id=1,
        name="Agent B",
        system_prompt="Prompt B",
        preferred_channel_session_id=channel_a.id,
    )
    session.add(channel_a)
    session.add(agent_b)
    session.commit()
    session.refresh(channel_a)
    session.refresh(agent_b)

    response = create_inbound_message(
        InboundCreateRequest(
            channel="whatsapp",
            external_message_id="msg_in_003",
            direction="inbound",
            sender_phone="601177777777",
            recipient_phone="601121000098",
            text_content="hello from channel B",
            channel_session_id=channel_a.id,
        ),
        session=session,
        auth=auth,
    )

    message = session.exec(
        select(UnifiedMessage).where(UnifiedMessage.id == response.message_id)
    ).first()
    lead = session.get(Lead, message.lead_id if message else None)
    thread = session.get(UnifiedThread, response.thread_id)

    rows_for_agent_b = list_ai_crm_threads(
        agent_id=int(agent_b.id),
        session=session,
        auth=auth,
    )
    rows_for_agent_a = list_ai_crm_threads(
        agent_id=1,
        session=session,
        auth=auth,
    )

    assert lead is not None
    assert lead.agent_id == agent_b.id
    assert thread is not None
    assert thread.agent_id == agent_b.id
    assert [row.thread_id for row in rows_for_agent_b] == [thread.id]
    assert rows_for_agent_a == []
