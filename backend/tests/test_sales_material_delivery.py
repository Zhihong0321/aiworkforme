from __future__ import annotations

from datetime import datetime

import pytest
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from src.adapters.db.agent_models import Agent, AgentSalesMaterial
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.messaging_models import OutboundQueue, UnifiedMessage, UnifiedThread
from src.adapters.db.tenant_models import Tenant
from src.app.background_tasks_inbound import _enqueue_sales_material_reply
from src.app.runtime.sales_materials import build_sales_material_prompt_block


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        tenant = Tenant(id=1, name="Tenant A")
        agent = Agent(id=1, tenant_id=1, name="Sales Agent", system_prompt="Helpful")
        workspace = Workspace(id=1, tenant_id=1, name="Workspace A", agent_id=1)
        lead = Lead(id=1, tenant_id=1, workspace_id=1, external_id="+15550001111", name="Lead A", agent_id=1)
        thread = UnifiedThread(id=1, tenant_id=1, lead_id=1, agent_id=1, channel="whatsapp")
        inbound = UnifiedMessage(
            id=1,
            tenant_id=1,
            lead_id=1,
            thread_id=1,
            channel="whatsapp",
            external_message_id="inbound-1",
            direction="inbound",
            message_type="text",
            text_content="Please send the brochure",
            delivery_status="received",
        )
        db.add(tenant)
        db.add(agent)
        db.add(workspace)
        db.add(lead)
        db.add(thread)
        db.add(inbound)
        db.commit()
        yield db


def test_enqueue_sales_material_reply_sends_uploaded_files_as_text_urls(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("APP_PUBLIC_BASE_URL", "https://public.example.com")
    inbound = session.get(UnifiedMessage, 1)
    material = AgentSalesMaterial(
        id=10,
        tenant_id=1,
        agent_id=1,
        filename="brochure.pdf",
        stored_name="abc-brochure.pdf",
        media_type="application/pdf",
        source_type="file",
        external_url="",
        file_size_bytes=123,
        description="Tiger Neo 3 brochure",
        public_token="abc123",
        public_url="http://127.0.0.1:8080/api/v1/public/sales-materials/abc123",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    outbound = _enqueue_sales_material_reply(
        session=session,
        inbound_message=inbound,
        agent_id=1,
        material=material,
        planner_trace={"reason": "explicit brochure request"},
    )

    saved = session.get(UnifiedMessage, outbound.id)
    queue = session.exec(select(OutboundQueue).where(OutboundQueue.message_id == outbound.id)).first()

    assert saved is not None
    assert saved.message_type == "text"
    assert saved.text_content == "https://public.example.com/api/v1/public/sales-materials/abc123"
    assert saved.media_url is None
    assert saved.raw_payload["url"] == saved.text_content
    assert saved.raw_payload["delivery_mode"] == "url_only"
    assert queue is not None
    assert queue.status == "queued"


def test_enqueue_sales_material_reply_sends_saved_links_as_text_urls(session: Session):
    inbound = session.get(UnifiedMessage, 1)
    material = AgentSalesMaterial(
        id=11,
        tenant_id=1,
        agent_id=1,
        filename="pricing.url",
        stored_name="",
        media_type="text/uri-list",
        source_type="url",
        external_url="https://example.com/pricing",
        file_size_bytes=27,
        description="Pricing page",
        public_token="",
        public_url="https://example.com/pricing",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    outbound = _enqueue_sales_material_reply(
        session=session,
        inbound_message=inbound,
        agent_id=1,
        material=material,
    )

    saved = session.get(UnifiedMessage, outbound.id)

    assert saved is not None
    assert saved.message_type == "text"
    assert saved.text_content == "https://example.com/pricing"
    assert saved.media_url is None
    assert saved.raw_payload["source_type"] == "url"
    assert saved.raw_payload["url"] == "https://example.com/pricing"


def test_sales_material_prompt_block_describes_url_only_delivery(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("APP_PUBLIC_BASE_URL", "https://public.example.com")
    material = AgentSalesMaterial(
        id=12,
        tenant_id=1,
        agent_id=1,
        filename="brochure.pdf",
        stored_name="abc-brochure.pdf",
        media_type="application/pdf",
        source_type="file",
        external_url="",
        file_size_bytes=123,
        description="Use when the customer asks for the brochure.",
        public_token="abc123",
        public_url="http://127.0.0.1:8080/api/v1/public/sales-materials/abc123",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    prompt_block = build_sales_material_prompt_block([material], sent_state={})

    assert "Every sales material is delivered as a follow-up message containing only its URL." in prompt_block
    assert "https://public.example.com/api/v1/public/sales-materials/abc123" in prompt_block
