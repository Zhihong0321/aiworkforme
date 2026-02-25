"""
MODULE: Messaging Router Schemas
PURPOSE: Request/response DTOs for unified messaging endpoints.
DOES: Define stable API payload and response models.
DOES NOT: Execute business logic or perform IO.
INVARIANTS: Field names/types remain backward-compatible.
SAFE CHANGE: Add backward-compatible fields only.
"""

from typing import Any, Dict, List, Optional

from sqlmodel import SQLModel

from src.adapters.db.messaging_models import UnifiedMessage


class OutboundCreateRequest(SQLModel):
    lead_id: int
    channel: str
    text_content: str
    channel_session_id: Optional[int] = None
    external_message_id: Optional[str] = None
    raw_payload: Dict[str, Any] = {}


class InboundCreateRequest(SQLModel):
    lead_id: Optional[int] = None
    channel: str
    external_message_id: str
    direction: str = "inbound"
    sender_phone: Optional[str] = None
    recipient_phone: Optional[str] = None
    text_content: Optional[str] = None
    message_type: str = "text"
    media_url: Optional[str] = None
    channel_session_id: Optional[int] = None
    raw_payload: Dict[str, Any] = {}


class MessageCreateResponse(SQLModel):
    message_id: int
    thread_id: Optional[int]
    queue_id: Optional[int] = None
    status: str


class DispatchResponse(SQLModel):
    queue_id: int
    message_id: int
    channel: str
    status: str
    retry_count: int
    detail: Optional[str] = None


class LeadWorkStartRequest(SQLModel):
    channel: str = "whatsapp"
    channel_session_id: Optional[int] = None


class LeadWorkStartResponse(SQLModel):
    lead_id: int
    message_id: int
    queue_id: int
    thread_id: int
    channel_session_id: int
    status: str
    detail: Optional[str] = None
    recipient: Optional[str] = None
    provider_message_id: Optional[str] = None


class WhatsAppConnectRequest(SQLModel):
    session_key: str = "primary"
    display_name: Optional[str] = None
    provider_base_url: Optional[str] = None


class WhatsAppRefreshResponse(SQLModel):
    channel_session_id: int
    session_identifier: str
    status: str
    remote: Dict[str, Any] = {}


class LeadThreadDetailResponse(SQLModel):
    thread_id: int
    lead_id: int
    channel: str
    status: str
    messages: List[UnifiedMessage]


class MVPOperationalCheckResponse(SQLModel):
    ready: bool
    checks: Dict[str, Any]
    blockers: List[str]


class InboundHealthResponse(SQLModel):
    ready: bool
    worker_mode: str
    notify_channel: str
    checks: Dict[str, Any]
    blockers: List[str]


class InboundDebugResponse(SQLModel):
    worker_state: Dict[str, Any]
    recent_inbound: List[Dict[str, Any]]
    recent_outbound_from_inbound: List[Dict[str, Any]]
    queue_snapshot: List[Dict[str, Any]]


class SimulateInboundRequest(SQLModel):
    lead_id: int
    text_content: str
    channel: str = "whatsapp"
    channel_session_id: Optional[int] = None


class SimulateInboundResponse(SQLModel):
    inbound_message_id: int
    thread_id: int
    inbound_status: str
    queued_reply_message_id: Optional[int] = None
    queued_reply_queue_id: Optional[int] = None
    detail: Optional[str] = None


class VoiceNoteTestRequest(SQLModel):
    lead_id: int
    channel_session_id: Optional[int] = None
    text_content: str = "Hey, quick voice note follow-up from me. Let me know if you'd like details."
    instructions: str = "Speak in a warm, natural, and persuasive sales tone."
    model: str = "qwen3-tts-flash"
    voice: str = "kiki"


class VoiceNoteTestResponse(SQLModel):
    success: bool
    lead_id: int
    channel_session_id: int
    recipient: str
    provider_message_id: Optional[str] = None
    local_message_id: Optional[int] = None
    tts_audio_bytes: int = 0
    tts_content_type: Optional[str] = None
    send_variant_used: Optional[str] = None
    detail: Optional[str] = None
    send_attempts: List[Dict[str, Any]] = []


class WhatsAppConversationImportRequest(SQLModel):
    channel_session_id: Optional[int] = None
    chat_limit: int = 200
    message_limit_per_chat: int = 100
    include_group_chats: bool = False
    seed_phone: Optional[str] = None
    seed_text: Optional[str] = None


class WhatsAppConversationImportResponse(SQLModel):
    workspace_id: int
    channel_session_id: int
    chats_scanned: int
    chats_imported: int
    leads_created: int
    threads_touched: int
    messages_created: int
    messages_skipped_existing: int
    lead_names_updated: int
    skipped_group_chats: int
    errors: List[str] = []
