from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from routers.messaging_helpers_validation import (
    extract_whatsapp_phone_from_payload,
    sync_whatsapp_channel_identity,
    upsert_whatsapp_channel_session,
    whatsapp_provider_session_identifier,
)


def _build_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_extract_whatsapp_phone_from_payload_prefers_whatsapp_jid_shapes():
    payload = {
        "status": "connected",
        "me": {"id": "601121000099@s.whatsapp.net"},
        "message": "Connected",
    }

    assert extract_whatsapp_phone_from_payload(payload) == "601121000099"


def test_upsert_whatsapp_channel_session_stores_description_in_metadata():
    session = _build_session()

    channel_session = upsert_whatsapp_channel_session(
        session=session,
        tenant_id=1,
        session_identifier="1:primary",
        display_name="Sales Team",
        description="Main Sales Line",
        provider_base_url="https://provider.example",
    )

    assert channel_session.display_name == "Sales Team"
    assert channel_session.session_metadata["description"] == "Main Sales Line"
    assert channel_session.session_metadata["provider_base_url"] == "https://provider.example"


def test_sync_whatsapp_channel_identity_promotes_phone_to_display_name_and_preserves_description():
    session = _build_session()
    channel_session = upsert_whatsapp_channel_session(
        session=session,
        tenant_id=1,
        session_identifier="1:primary",
        display_name="Primary WhatsApp",
        description="Primary WhatsApp",
        provider_base_url=None,
    )

    changed = sync_whatsapp_channel_identity(
        channel_session,
        provider_payload={"me": {"id": "601121000099@s.whatsapp.net"}},
        provider_session_id="1:primary",
    )

    assert changed is True
    assert channel_session.session_identifier == "601121000099"
    assert channel_session.display_name == "601121000099"
    assert channel_session.session_metadata["description"] == "Primary WhatsApp"
    assert channel_session.session_metadata["connected_number"] == "601121000099"
    assert channel_session.session_metadata["provider_session_id"] == "1:primary"


def test_upsert_whatsapp_channel_session_reuses_row_by_provider_session_id_after_identity_sync():
    session = _build_session()
    channel_session = upsert_whatsapp_channel_session(
        session=session,
        tenant_id=1,
        session_identifier="1:primary",
        display_name="Primary WhatsApp",
        description="Primary WhatsApp",
        provider_base_url=None,
    )
    sync_whatsapp_channel_identity(
        channel_session,
        explicit_phone="601121000099",
        provider_session_id="1:primary",
    )
    session.add(channel_session)
    session.commit()
    session.refresh(channel_session)

    reused = upsert_whatsapp_channel_session(
        session=session,
        tenant_id=1,
        session_identifier="1:primary",
        display_name=None,
        description="Updated Description",
        provider_base_url=None,
    )

    assert reused.id == channel_session.id
    assert reused.session_identifier == "601121000099"
    assert whatsapp_provider_session_identifier(reused) == "1:primary"
    assert reused.session_metadata["description"] == "Updated Description"
