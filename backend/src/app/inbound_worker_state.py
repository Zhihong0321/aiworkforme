"""
MODULE: Inbound Worker State
PURPOSE: Shared state and helpers for inbound worker observability.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


INBOUND_WORKER_STATE: Dict[str, Any] = {
    "started_at": None,
    "last_loop_at": None,
    "last_listen_connected_at": None,
    "last_notify_received_at": None,
    "last_notified_message_id": None,
    "last_claimed_at": None,
    "last_claimed_message_id": None,
    "last_processed_at": None,
    "last_processed_message_id": None,
    "last_error_at": None,
    "last_error_message": None,
    "notify_events_total": 0,
    "claimed_total": 0,
    "processed_total": 0,
    "errors_total": 0,
}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mark_worker_state(worker_state: Dict[str, Any], **kwargs: Any) -> None:
    worker_state.update(kwargs)


def get_worker_state_snapshot(worker_state: Dict[str, Any]) -> Dict[str, Any]:
    return dict(worker_state)
