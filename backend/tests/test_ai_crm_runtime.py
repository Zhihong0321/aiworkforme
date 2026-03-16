from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine, select

from routers.ai_crm_runtime import scan_agent_threads, trigger_due_followups
from src.adapters.db.agent_models import Agent
from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.crm_models import (
    AICRMAggressiveness,
    AICRMFollowupMessageType,
    AICRMFollowupStrategy,
    AICRMLeadStatus,
    AICRMThreadState,
    AgentCRMProfile,
    Lead,
    Workspace,
)
from src.adapters.db.messaging_models import OutboundQueue, UnifiedMessage, UnifiedThread
from src.adapters.db.tenant_models import Tenant


class _FakeRouter:
    def __init__(self, *contents: str):
        self.contents = list(contents)
        self.calls = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        content = self.contents.pop(0) if self.contents else ""
        return SimpleNamespace(content=content, provider_info={}, usage={})


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_thread(
    session: Session,
    *,
    tenant_id: int = 1,
    agent_id: int = 101,
    review_after_hours: int = 24,
    allow_voice_notes: bool = False,
) -> tuple[Tenant, Agent, Workspace, Lead, UnifiedThread, AgentCRMProfile]:
    tenant = Tenant(id=tenant_id, name=f"Tenant {tenant_id}")
    agent = Agent(id=agent_id, tenant_id=tenant_id, name=f"Agent {agent_id}", system_prompt="Helpfully sell")
    workspace = Workspace(id=tenant_id, tenant_id=tenant_id, name=f"Workspace {tenant_id}", agent_id=agent_id)
    lead = Lead(
        id=tenant_id,
        tenant_id=tenant_id,
        workspace_id=workspace.id,
        agent_id=agent_id,
        external_id=f"{tenant_id}234567890@s.whatsapp.net",
        name="Casey Lead",
    )
    thread = UnifiedThread(
        id=tenant_id,
        tenant_id=tenant_id,
        lead_id=lead.id,
        agent_id=agent_id,
        channel="whatsapp",
        status="active",
    )
    control = AgentCRMProfile(
        tenant_id=tenant_id,
        agent_id=agent_id,
        enabled=True,
        scan_frequency_messages=4,
        aggressiveness=AICRMAggressiveness.BALANCED,
        review_after_hours=review_after_hours,
        allow_voice_notes=allow_voice_notes,
        not_interested_strategy=AICRMFollowupStrategy.PROMO,
        rejected_strategy=AICRMFollowupStrategy.DISCOUNT,
        double_reject_strategy=AICRMFollowupStrategy.STOP,
    )
    session.add(tenant)
    session.add(agent)
    session.add(workspace)
    session.add(lead)
    session.add(thread)
    session.add(control)
    session.commit()
    return tenant, agent, workspace, lead, thread, control


def test_scan_agent_threads_reviews_only_dormant_outbound_and_uses_ai_schedule():
    session = _make_session()
    _, agent, _, lead, thread, _ = _seed_thread(
        session,
        tenant_id=11,
        agent_id=211,
        review_after_hours=12,
        allow_voice_notes=True,
    )
    now = datetime.utcnow()
    session.add(
        UnifiedMessage(
            tenant_id=lead.tenant_id,
            lead_id=lead.id,
            thread_id=thread.id,
            channel="whatsapp",
            external_message_id="m1",
            direction="inbound",
            text_content="I will be overseas next week, maybe message me after that.",
            created_at=now - timedelta(hours=31),
            updated_at=now - timedelta(hours=31),
        )
    )
    session.add(
        UnifiedMessage(
            tenant_id=lead.tenant_id,
            lead_id=lead.id,
            thread_id=thread.id,
            channel="whatsapp",
            external_message_id="m2",
            direction="outbound",
            text_content="Sure, I will follow up later.",
            created_at=now - timedelta(hours=30),
            updated_at=now - timedelta(hours=30),
        )
    )
    session.commit()

    router = _FakeRouter(
        '{"status":"CONSIDERING","customer_reaction":"travelling","summary":"Lead asked for a follow-up after the trip.","should_follow_up":true,"recommended_wait_hours":168,"recommended_message_type":"audio"}'
    )

    result = __import__("asyncio").run(
        scan_agent_threads(
            session=session,
            router=router,
            tenant_id=int(lead.tenant_id),
            agent_id=int(agent.id),
            force_all=False,
        )
    )

    state = session.exec(select(AICRMThreadState).where(AICRMThreadState.thread_id == thread.id)).first()
    assert result.scanned_threads == 1
    assert result.skipped_threads == 0
    assert result.next_followups_set == 1
    assert state is not None
    assert state.agent_id == agent.id
    assert state.status == AICRMLeadStatus.CONSIDERING
    assert state.followup_message_type == AICRMFollowupMessageType.AUDIO
    assert state.next_followup_at is not None
    assert state.last_scanned_at is not None
    assert timedelta(hours=167) <= (state.next_followup_at - state.last_scanned_at) <= timedelta(hours=169)
    session.refresh(lead)
    assert lead.next_followup_at == state.next_followup_at
    assert lead.last_followup_review_at is not None


def test_trigger_due_followups_skips_and_clears_state_when_customer_already_replied():
    session = _make_session()
    _, agent, _, lead, thread, _ = _seed_thread(
        session,
        tenant_id=12,
        agent_id=212,
        review_after_hours=6,
        allow_voice_notes=False,
    )
    now = datetime.utcnow()
    session.add(
        UnifiedMessage(
            tenant_id=lead.tenant_id,
            lead_id=lead.id,
            thread_id=thread.id,
            channel="whatsapp",
            external_message_id="m1",
            direction="outbound",
            text_content="Checking in on this.",
            created_at=now - timedelta(hours=10),
            updated_at=now - timedelta(hours=10),
        )
    )
    session.add(
        UnifiedMessage(
            tenant_id=lead.tenant_id,
            lead_id=lead.id,
            thread_id=thread.id,
            channel="whatsapp",
            external_message_id="m2",
            direction="inbound",
            text_content="Thanks, I will reply later today.",
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),
        )
    )
    state = AICRMThreadState(
        tenant_id=lead.tenant_id,
        workspace_id=lead.workspace_id,
        agent_id=agent.id,
        thread_id=thread.id,
        lead_id=lead.id,
        status=AICRMLeadStatus.NO_RESPONSE,
        followup_strategy=AICRMFollowupStrategy.PROMO,
        followup_message_type=AICRMFollowupMessageType.TEXT,
        aggressiveness=AICRMAggressiveness.BALANCED,
        next_followup_at=now - timedelta(minutes=5),
    )
    lead.next_followup_at = state.next_followup_at
    session.add(state)
    session.add(lead)
    session.commit()

    result = __import__("asyncio").run(
        trigger_due_followups(
            session=session,
            router=_FakeRouter("unused"),
            tenant_id=int(lead.tenant_id),
            agent_id=int(agent.id),
        )
    )

    session.refresh(state)
    session.refresh(lead)
    queued = session.exec(select(OutboundQueue)).all()
    assert result.triggered == 0
    assert result.skipped == 1
    assert state.next_followup_at is None
    assert lead.next_followup_at is None
    assert queued == []


def test_trigger_due_followups_enqueues_audio_message_when_allowed():
    session = _make_session()
    _, agent, _, lead, thread, _ = _seed_thread(
        session,
        tenant_id=13,
        agent_id=213,
        review_after_hours=24,
        allow_voice_notes=True,
    )
    channel = ChannelSession(
        tenant_id=lead.tenant_id,
        channel_type=ChannelType.WHATSAPP,
        session_identifier="session-13",
        display_name="Sales WA",
        status=SessionStatus.ACTIVE,
        session_metadata={},
    )
    now = datetime.utcnow()
    session.add(channel)
    session.commit()
    session.refresh(channel)
    agent.preferred_channel_session_id = channel.id
    session.add(agent)
    session.add(
        UnifiedMessage(
            tenant_id=lead.tenant_id,
            lead_id=lead.id,
            thread_id=thread.id,
            channel="whatsapp",
            external_message_id="m1",
            direction="inbound",
            text_content="I am still thinking about it.",
            created_at=now - timedelta(hours=50),
            updated_at=now - timedelta(hours=50),
        )
    )
    session.add(
        UnifiedMessage(
            tenant_id=lead.tenant_id,
            lead_id=lead.id,
            thread_id=thread.id,
            channel="whatsapp",
            external_message_id="m2",
            direction="outbound",
            text_content="Happy to answer any question.",
            created_at=now - timedelta(hours=30),
            updated_at=now - timedelta(hours=30),
        )
    )
    state = AICRMThreadState(
        tenant_id=lead.tenant_id,
        workspace_id=lead.workspace_id,
        agent_id=agent.id,
        thread_id=thread.id,
        lead_id=lead.id,
        status=AICRMLeadStatus.CONSIDERING,
        followup_strategy=AICRMFollowupStrategy.PROMO,
        followup_message_type=AICRMFollowupMessageType.AUDIO,
        aggressiveness=AICRMAggressiveness.BALANCED,
        next_followup_at=now - timedelta(minutes=5),
    )
    session.add(state)
    session.add(lead)
    session.commit()

    result = __import__("asyncio").run(
        trigger_due_followups(
            session=session,
            router=_FakeRouter("Quick voice note: just checking whether timing is better now."),
            tenant_id=int(lead.tenant_id),
            agent_id=int(agent.id),
        )
    )

    session.refresh(state)
    outbound = session.exec(
        select(UnifiedMessage)
        .where(
            UnifiedMessage.thread_id == thread.id,
            UnifiedMessage.direction == "outbound",
            UnifiedMessage.external_message_id != "m2",
        )
    ).first()
    queue = session.exec(select(OutboundQueue)).first()

    assert result.triggered == 1
    assert result.skipped == 0
    assert outbound is not None
    assert outbound.message_type == "audio"
    assert outbound.raw_payload["source"] == "ai_crm_followup"
    assert outbound.raw_payload["followup_message_type"] == "audio"
    assert outbound.raw_payload["tts_model"] == "qwen3-tts-flash"
    assert queue is not None
    assert queue.message_id == outbound.id
    assert state.next_followup_at is None
