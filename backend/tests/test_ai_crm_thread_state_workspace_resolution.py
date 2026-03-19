from __future__ import annotations

from datetime import datetime

from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from routers.ai_crm_helpers import upsert_thread_state
from src.adapters.db.agent_models import Agent
from src.adapters.db.crm_models import AICRMThreadState, Lead, Workspace
from src.adapters.db.tenant_models import Tenant


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


def test_upsert_thread_state_repairs_missing_lead_workspace_from_agent_workspace():
    session = _make_session()
    now = datetime.utcnow()

    agent = Agent(id=101, tenant_id=1, name="Agent A", system_prompt="Prompt A")
    workspace = Workspace(id=201, tenant_id=1, name="Agent Workspace", agent_id=agent.id)
    lead = Lead(
        id=301,
        tenant_id=1,
        workspace_id=None,
        agent_id=agent.id,
        external_id="601188888888",
        name="Lead A",
        created_at=now,
    )
    session.add(agent)
    session.add(workspace)
    session.add(lead)
    session.commit()

    state = upsert_thread_state(
        session=session,
        tenant_id=1,
        agent_id=agent.id,
        thread_id=401,
        lead_id=lead.id,
        workspace_id=None,
    )

    session.refresh(lead)
    stored_state = session.exec(
        select(AICRMThreadState).where(AICRMThreadState.id == state.id)
    ).first()

    assert stored_state is not None
    assert stored_state.workspace_id == workspace.id
    assert lead.workspace_id == workspace.id
