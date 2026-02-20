"""
MODULE: Inbound Worker Notify
PURPOSE: PostgreSQL LISTEN/NOTIFY helpers for inbound worker wake-ups.
"""

from __future__ import annotations

import json
import select as pyselect
from typing import Any, Callable, Dict, List


def open_inbound_listen_connection(
    *,
    engine: Any,
    inbound_notify_channel: str,
    mark_worker_state: Callable[..., None],
    iso_now: Callable[[], str],
    logger: Any,
) -> Any:
    if engine.dialect.name != "postgresql":
        return None

    raw_conn = engine.raw_connection()
    raw_conn.autocommit = True
    cursor = raw_conn.cursor()
    try:
        cursor.execute(f"LISTEN {inbound_notify_channel};")
    finally:
        cursor.close()
    mark_worker_state(last_listen_connected_at=iso_now())
    logger.info(
        "Inbound worker listening on PostgreSQL channel: %s",
        inbound_notify_channel,
    )
    return raw_conn


def wait_for_inbound_notify(
    listen_conn: Any,
    timeout_seconds: float,
    *,
    mark_worker_state: Callable[..., None],
    worker_state: Dict[str, Any],
    iso_now: Callable[[], str],
    logger: Any,
) -> List[int]:
    """
    Blocks up to timeout_seconds for Postgres NOTIFY and returns message ids.
    Payload format: {"message_id": <int>, ...}
    """
    if not listen_conn:
        return []

    message_ids: List[int] = []
    try:
        ready, _, _ = pyselect.select([listen_conn], [], [], timeout_seconds)
        if not ready:
            return []

        listen_conn.poll()
        notifications = list(getattr(listen_conn, "notifies", []) or [])
        if hasattr(listen_conn, "notifies"):
            listen_conn.notifies.clear()

        for notify in notifications:
            payload = getattr(notify, "payload", "") or ""
            if not payload:
                continue
            try:
                data = json.loads(payload)
                message_id = int(data.get("message_id"))
            except Exception:
                logger.warning("Inbound NOTIFY payload parse failed: %s", payload)
                continue
            if message_id > 0:
                mark_worker_state(
                    last_notify_received_at=iso_now(),
                    last_notified_message_id=message_id,
                    notify_events_total=worker_state.get("notify_events_total", 0) + 1,
                )
                message_ids.append(message_id)
    except Exception as exc:
        logger.warning("Inbound NOTIFY wait failed: %s", exc)
    return message_ids
