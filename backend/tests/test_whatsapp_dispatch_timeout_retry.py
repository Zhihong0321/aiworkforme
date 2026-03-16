from __future__ import annotations

from datetime import datetime

import httpx
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from routers.messaging_runtime import dispatch_next_outbound_for_tenant
from src.adapters.db.crm_models import Lead
from src.adapters.db.messaging_models import OutboundQueue, UnifiedMessage
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


def test_whatsapp_read_timeout_does_not_retry_and_risk_duplicate_send(monkeypatch):
    session = _make_session()
    now = datetime.utcnow()

    lead = Lead(
        tenant_id=1,
        external_id="+15550001111",
        name="Lead A",
    )
    session.add(lead)
    session.commit()
    session.refresh(lead)

    message = UnifiedMessage(
        tenant_id=1,
        lead_id=int(lead.id),
        thread_id=None,
        channel_session_id=None,
        channel="whatsapp",
        external_message_id="out_timeout_1",
        direction="outbound",
        message_type="image",
        text_content=None,
        media_url="https://example.test/namecard.png",
        raw_payload={"source": "ai_agent_sales_material"},
        delivery_status="queued",
        created_at=now,
        updated_at=now,
    )
    session.add(message)
    session.commit()
    session.refresh(message)

    queue = OutboundQueue(
        tenant_id=1,
        message_id=int(message.id),
        channel="whatsapp",
        channel_session_id=None,
        status="queued",
        retry_count=0,
        next_attempt_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(queue)
    session.commit()

    monkeypatch.setattr(
        "routers.messaging_runtime.send_to_channel",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(httpx.ReadTimeout("The read operation timed out")),
    )

    result = dispatch_next_outbound_for_tenant(session, 1)
    refreshed_queue = session.get(OutboundQueue, int(queue.id))
    refreshed_message = session.get(UnifiedMessage, int(message.id))

    assert result is not None
    assert result.status == "accepted"
    assert refreshed_queue is not None
    assert refreshed_queue.status == "accepted"
    assert refreshed_queue.retry_count == 0
    assert refreshed_queue.last_error == "The read operation timed out"
    assert refreshed_message is not None
    assert refreshed_message.delivery_status == "provider_accepted"
    assert refreshed_message.raw_payload["provider_status"] == "timeout_assumed_pending"
    assert "retry suppressed" in refreshed_message.raw_payload["dispatch_warning"].lower()
