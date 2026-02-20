"""
MODULE: AI CRM Schemas
PURPOSE: Request/response DTOs for AI CRM endpoints.
DOES: Define stable API payload contracts.
DOES NOT: Execute workflow logic or DB operations.
INVARIANTS: Field names/types remain backward-compatible.
SAFE CHANGE: Add fields in backward-compatible ways only.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlmodel import SQLModel


class AICRMControlUpdateRequest(SQLModel):
    enabled: bool = True
    scan_frequency_messages: int = 4
    aggressiveness: str = "BALANCED"
    not_interested_strategy: str = "PROMO"
    rejected_strategy: str = "DISCOUNT"
    double_reject_strategy: str = "STOP"


class AICRMControlResponse(SQLModel):
    enabled: bool
    scan_frequency_messages: int
    aggressiveness: str
    not_interested_strategy: str
    rejected_strategy: str
    double_reject_strategy: str


class AICRMThreadRow(SQLModel):
    thread_id: int
    lead_id: int
    lead_name: Optional[str]
    lead_external_id: str
    total_messages: int
    status: str
    customer_reaction: Optional[str]
    summary: Optional[str]
    reject_count: int
    followup_strategy: str
    aggressiveness: str
    next_followup_at: Optional[datetime]
    last_scanned_at: Optional[datetime]
    last_scanned_message_count: int
    pending_scan: bool
    last_message_preview: Optional[str]
    last_message_direction: Optional[str]
    last_message_at: Optional[datetime]
    reason_trace: Optional[Dict[str, Any]]


class AICRMScanRequest(SQLModel):
    force_all: bool = False


class AICRMScanResponse(SQLModel):
    workspace_id: int
    scanned_threads: int
    skipped_threads: int
    next_followups_set: int
    errors: List[str]


class AICRMTriggerResponse(SQLModel):
    workspace_id: int
    triggered: int
    skipped: int
    errors: List[str]


class AICRMFastForwardRequest(SQLModel):
    seconds: int = 5
    include_overdue: bool = True


class AICRMFastForwardResponse(SQLModel):
    workspace_id: int
    seconds: int
    target_followup_at: datetime
    updated_states: int
