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
    lead_id: int
    channel: str
    external_message_id: str
    text_content: Optional[str] = None
    message_type: str = "text"
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
