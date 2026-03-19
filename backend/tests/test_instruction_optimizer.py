from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from routers.agents import optimize_agent_instruction
from src.adapters.api.dependencies import AuthContext
from src.adapters.db.agent_models import Agent, AgentInstructionOptimizeRequest
from src.adapters.db.crm_models import Lead
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


class _FakeRouter:
    def __init__(self):
        self.calls = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        payload = {
            "summary": "Prompt was too vague about escalation and tone.",
            "diagnosis": ["The agent had no concrete escalation trigger."],
            "instruction_changes": ["Add explicit escalation rules and concise reply guardrails."],
            "knowledge_updates": ["Add a worked example for objection handling."],
            "warnings": [],
            "optimized_system_prompt": "You are a concise sales assistant. Escalate when pricing or policy is uncertain.",
        }
        return SimpleNamespace(
            content=json.dumps(payload),
            provider_info={"provider": "uniapi", "model": "gemini-3.1-flash-lite-preview"},
        )


@pytest.mark.asyncio
async def test_instruction_optimizer_uses_agent_thread_context():
    session = _make_session()
    auth = _auth_context()
    now = datetime.utcnow()

    agent = Agent(id=101, tenant_id=1, name="Closer", system_prompt="Be helpful.")
    lead = Lead(id=301, tenant_id=1, workspace_id=None, agent_id=agent.id, external_id="601188888888", name="Lead")
    thread = UnifiedThread(
        id=401,
        tenant_id=1,
        lead_id=lead.id,
        agent_id=agent.id,
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
        channel_session_id=None,
        channel="whatsapp",
        external_message_id="in_1",
        direction="inbound",
        message_type="text",
        text_content="You sound robotic. Can I talk to a human?",
        delivery_status="received",
        created_at=now,
        updated_at=now,
    )
    session.add(agent)
    session.add(lead)
    session.add(thread)
    session.add(inbound)
    session.commit()

    fake_router = _FakeRouter()
    result = await optimize_agent_instruction(
        agent_id=agent.id,
        payload=AgentInstructionOptimizeRequest(
            feedback="The replies felt robotic and did not escalate to a human.",
            thread_id=thread.id,
            max_thread_messages=10,
        ),
        session=session,
        llm_router=fake_router,
        auth=auth,
    )

    assert result.agent_id == agent.id
    assert result.context_source == "stored_thread"
    assert result.used_thread_id == thread.id
    assert "escalation" in result.summary.lower()
    assert result.optimized_system_prompt.startswith("You are a concise sales assistant")

    sent_messages = fake_router.calls[0]["messages"]
    joined = "\n".join(item["content"] for item in sent_messages)
    assert "You sound robotic. Can I talk to a human?" in joined
    assert "EFFECTIVE COMPOSED SYSTEM PROMPT" in joined


@pytest.mark.asyncio
async def test_instruction_optimizer_rejects_thread_from_other_agent():
    session = _make_session()
    auth = _auth_context()
    now = datetime.utcnow()

    agent = Agent(id=101, tenant_id=1, name="Closer", system_prompt="Be helpful.")
    other_agent = Agent(id=102, tenant_id=1, name="Support", system_prompt="Be calm.")
    lead = Lead(id=301, tenant_id=1, workspace_id=None, agent_id=other_agent.id, external_id="601177777777", name="Lead")
    thread = UnifiedThread(
        id=401,
        tenant_id=1,
        lead_id=lead.id,
        agent_id=other_agent.id,
        channel="whatsapp",
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(agent)
    session.add(other_agent)
    session.add(lead)
    session.add(thread)
    session.commit()

    with pytest.raises(HTTPException) as exc:
        await optimize_agent_instruction(
            agent_id=agent.id,
            payload=AgentInstructionOptimizeRequest(
                feedback="Bad performance.",
                thread_id=thread.id,
            ),
            session=session,
            llm_router=_FakeRouter(),
            auth=auth,
        )

    assert exc.value.status_code == 404
