from __future__ import annotations

from typing import Any, Dict

from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from routers import messaging_runtime
from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.messaging_models import UnifiedMessage
from src.adapters.db.tenant_models import Tenant
from src.adapters.db.user_models import User


def _build_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    db = Session(engine)
    db.add(Tenant(id=1, name="Tenant A"))
    db.add(User(id=10, email="tenant@test.local", password_hash="x", is_active=True))
    db.add(Workspace(id=1, tenant_id=1, name="Main"))
    db.add(
        Lead(
            id=1,
            tenant_id=1,
            workspace_id=1,
            external_id="601121000099",
            name="Lead A",
            stage="NEW",
        )
    )
    db.add(
        ChannelSession(
            id=2,
            tenant_id=1,
            channel_type=ChannelType.WHATSAPP,
            session_identifier="1:primary",
            status=SessionStatus.ACTIVE,
            session_metadata={"provider_base_url": "https://example.test"},
        )
    )
    db.commit()
    return db


def test_send_whatsapp_message_audio_uses_generated_voice_note(monkeypatch):
    session = _build_session()
    message = UnifiedMessage(
        id=5,
        tenant_id=1,
        lead_id=1,
        channel_session_id=2,
        channel="whatsapp",
        external_message_id="out_001",
        direction="outbound",
        message_type="audio",
        text_content="Please send this as a voice note.",
        raw_payload={"tts_model": "qwen3-tts-flash", "tts_voice": "kiki"},
        delivery_status="queued",
    )

    called: Dict[str, Any] = {}

    def fake_dispatch_generated_voice_note(**kwargs):
        called.update(kwargs)
        return {
            "provider_message_id": "voice_msg_001",
            "remote_jid": "601121000099@s.whatsapp.net",
            "temp_media_url": "https://files.example.test/voice-note.ogg",
            "tts_content_type": "audio/ogg; codecs=opus",
            "send_variant_used": "audio_url_ptt",
            "send_attempts": [{"variant": "audio_url_ptt", "status_code": 200}],
        }

    monkeypatch.setattr(messaging_runtime, "dispatch_generated_voice_note", fake_dispatch_generated_voice_note)

    provider_message_id = messaging_runtime.send_whatsapp_message(session, message)

    assert provider_message_id == "voice_msg_001"
    assert called["text_content"] == "Please send this as a voice note."
    assert message.media_url == "https://files.example.test/voice-note.ogg"
    assert message.raw_payload["provider_message_id"] == "voice_msg_001"
    assert message.raw_payload["tts_voice"] == "kiki"


def test_send_whatsapp_message_audio_with_public_url_uses_voice_sender(monkeypatch):
    session = _build_session()
    message = UnifiedMessage(
        id=6,
        tenant_id=1,
        lead_id=1,
        channel_session_id=2,
        channel="whatsapp",
        external_message_id="out_002",
        direction="outbound",
        message_type="audio",
        text_content="Ignored when media_url is already public",
        media_url="https://files.example.test/already-public.ogg",
        raw_payload={"tts_content_type": "audio/ogg; codecs=opus"},
        delivery_status="queued",
    )

    called: Dict[str, Any] = {}

    def fake_send_whatsapp_voice_note(**kwargs):
        called["send"] = kwargs
        return {
            "provider_message_id": "voice_msg_002",
            "remote_jid": "601121000099@s.whatsapp.net",
            "send_variant_used": "audio_url_ptt",
            "send_attempts": [{"variant": "audio_url_ptt", "status_code": 200}],
        }

    def fake_verify_whatsapp_message_visible(**kwargs):
        called["verify"] = kwargs

    monkeypatch.setattr(messaging_runtime, "send_whatsapp_voice_note", fake_send_whatsapp_voice_note)
    monkeypatch.setattr(messaging_runtime, "verify_whatsapp_message_visible", fake_verify_whatsapp_message_visible)

    provider_message_id = messaging_runtime.send_whatsapp_message(session, message)

    assert provider_message_id == "voice_msg_002"
    assert called["send"]["audio_url"] == "https://files.example.test/already-public.ogg"
    assert called["verify"]["provider_message_id"] == "voice_msg_002"
    assert message.raw_payload["provider_message_id"] == "voice_msg_002"
