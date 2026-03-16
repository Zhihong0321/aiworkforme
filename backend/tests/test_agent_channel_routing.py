from __future__ import annotations

import asyncio
from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine, select

from routers.ai_crm_helpers import resolve_channel_session_id
from routers.messaging_core_routes import start_lead_work
from routers.messaging_schemas import LeadWorkStartRequest
from src.adapters.db.agent_models import Agent
from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.messaging_models import OutboundQueue, UnifiedMessage, UnifiedThread
from src.adapters.db.tenant_models import Tenant


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_agent_channels_and_thread(
    session: Session,
    *,
    preferred_status: SessionStatus = SessionStatus.ACTIVE,
) -> tuple[Tenant, Agent, Lead, UnifiedThread, ChannelSession, ChannelSession]:
    tenant = Tenant(id=41, name="Tenant 41")
    session.add(tenant)

    channel_a = ChannelSession(
        tenant_id=tenant.id,
        channel_type=ChannelType.WHATSAPP,
        session_identifier="channel-a",
        display_name="Channel A",
        status=SessionStatus.ACTIVE,
        session_metadata={},
    )
    channel_b = ChannelSession(
        tenant_id=tenant.id,
        channel_type=ChannelType.WHATSAPP,
        session_identifier="channel-b",
        display_name="Channel B",
        status=preferred_status,
        session_metadata={},
    )
    session.add(channel_a)
    session.add(channel_b)
    session.commit()
    session.refresh(channel_a)
    session.refresh(channel_b)

    agent = Agent(
        id=141,
        tenant_id=tenant.id,
        name="Closer",
        system_prompt="Helpfully sell",
        preferred_channel_session_id=channel_b.id,
    )
    workspace = Workspace(id=241, tenant_id=tenant.id, name="WS", agent_id=agent.id)
    lead = Lead(
        id=341,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        agent_id=agent.id,
        external_id="60123456789",
        name="Casey",
        stage="NEW",
    )
    thread = UnifiedThread(
        id=441,
        tenant_id=tenant.id,
        lead_id=lead.id,
        agent_id=agent.id,
        channel="whatsapp",
        channel_session_id=channel_a.id,
        status="active",
    )
    session.add(agent)
    session.add(workspace)
    session.add(lead)
    session.add(thread)
    session.commit()
    session.refresh(agent)
    session.refresh(lead)
    session.refresh(thread)
    return tenant, agent, lead, thread, channel_a, channel_b


def test_resolve_channel_session_id_uses_only_agent_assigned_channel():
    session = _make_session()
    tenant, agent, _, thread, channel_a, channel_b = _seed_agent_channels_and_thread(session)

    resolved = resolve_channel_session_id(
        session=session,
        tenant_id=int(tenant.id),
        channel="whatsapp",
        agent_id=int(agent.id),
        fallback_channel_session_id=int(channel_a.id),
    )

    assert resolved == channel_b.id
    assert resolved != channel_a.id


def test_resolve_channel_session_id_stops_when_assigned_channel_is_not_active():
    session = _make_session()
    tenant, agent, _, thread, channel_a, channel_b = _seed_agent_channels_and_thread(
        session,
        preferred_status=SessionStatus.DISCONNECTED,
    )

    resolved = resolve_channel_session_id(
        session=session,
        tenant_id=int(tenant.id),
        channel="whatsapp",
        agent_id=int(agent.id),
        fallback_channel_session_id=int(channel_a.id),
    )

    assert resolved is None
    assert channel_a.status == SessionStatus.ACTIVE
    assert channel_b.status == SessionStatus.DISCONNECTED


def test_resolve_channel_session_id_returns_none_when_agent_has_no_assigned_channel():
    session = _make_session()
    tenant, agent, _, _, channel_a, _ = _seed_agent_channels_and_thread(session)
    agent.preferred_channel_session_id = None
    session.add(agent)
    session.commit()

    resolved = resolve_channel_session_id(
        session=session,
        tenant_id=int(tenant.id),
        channel="whatsapp",
        agent_id=int(agent.id),
        fallback_channel_session_id=int(channel_a.id),
    )

    assert resolved is None


def test_start_lead_work_uses_agent_preferred_channel_when_payload_omits_channel_session_id(monkeypatch):
    session = _make_session()
    tenant, agent, lead, thread, channel_a, channel_b = _seed_agent_channels_and_thread(session)

    async def _fake_generate_initial_outreach_text(router, agent_obj, lead_obj, include_context_prompt):
        assert agent_obj.id == agent.id
        assert lead_obj.id == lead.id
        return "Hello from the assigned channel.", {"provider": "test", "model": "fake", "usage": {}}

    monkeypatch.setattr(
        "routers.messaging_core_routes._generate_initial_outreach_text",
        _fake_generate_initial_outreach_text,
    )
    monkeypatch.setattr(
        "routers.messaging_core_routes.dispatch_next_outbound_for_tenant",
        lambda session_obj, tenant_id: None,
    )

    auth = SimpleNamespace(tenant=SimpleNamespace(id=tenant.id))
    response = asyncio.run(
        start_lead_work(
            lead_id=int(lead.id),
            payload=LeadWorkStartRequest(channel="whatsapp"),
            session=session,
            auth=auth,
            router=SimpleNamespace(),
        )
    )

    outbound = session.exec(
        select(UnifiedMessage).where(
            UnifiedMessage.lead_id == lead.id,
            UnifiedMessage.direction == "outbound",
        )
    ).first()
    queue = session.exec(select(OutboundQueue).where(OutboundQueue.message_id == outbound.id)).first()

    assert response.channel_session_id == channel_b.id
    assert response.channel_session_id != channel_a.id
    assert outbound is not None
    assert outbound.channel_session_id == channel_b.id
    assert queue is not None
    assert queue.channel_session_id == channel_b.id
