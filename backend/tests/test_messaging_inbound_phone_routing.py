from __future__ import annotations

from fastapi import HTTPException
import pytest
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from routers.messaging_core_routes import create_inbound_message
from routers.messaging_schemas import InboundCreateRequest
from src.adapters.api.dependencies import AuthContext
from src.adapters.db.agent_models import Agent
from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.messaging_models import UnifiedMessage
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


def test_inbound_requires_session_when_phone_cannot_map():
    session = _build_session()
    auth = _build_auth()

    with pytest.raises(HTTPException) as exc:
        create_inbound_message(
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

    assert exc.value.status_code == 400
    assert "channel session" in str(exc.value.detail).lower()
