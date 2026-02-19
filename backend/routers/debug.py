"""
Temporary debug routes for production diagnosis.
Remove after inbound pipeline stabilization.
"""
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlmodel import Session, select

from src.infra.database import get_session
from src.adapters.db.messaging_models import UnifiedMessage, OutboundQueue
from src.app.background_tasks_inbound import get_inbound_worker_debug_snapshot


router = APIRouter(prefix="/api/v1/debug", tags=["Debug"])


def _require_debug_key(x_debug_key: Optional[str] = Header(default=None, alias="X-Debug-Key")):
    expected = os.getenv("DEBUG_ENDPOINT_KEY")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Debug endpoint disabled (DEBUG_ENDPOINT_KEY not configured).",
        )
    if x_debug_key != expected:
        raise HTTPException(status_code=401, detail="Invalid debug key")


@router.get("/inbound")
def inbound_debug(
    tenant_id: Optional[int] = Query(default=None, description="Optional tenant filter"),
    _: None = Depends(_require_debug_key),
    session: Session = Depends(get_session),
):
    inbound_query = select(UnifiedMessage).where(UnifiedMessage.direction == "inbound")
    outbound_query = select(UnifiedMessage).where(UnifiedMessage.direction == "outbound")
    queue_query = select(OutboundQueue)
    if tenant_id is not None:
        inbound_query = inbound_query.where(UnifiedMessage.tenant_id == tenant_id)
        outbound_query = outbound_query.where(UnifiedMessage.tenant_id == tenant_id)
        queue_query = queue_query.where(OutboundQueue.tenant_id == tenant_id)

    recent_inbound_rows = session.exec(
        inbound_query.order_by(UnifiedMessage.id.desc()).limit(30)
    ).all()
    recent_inbound: List[Dict[str, Any]] = [
        {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "thread_id": row.thread_id,
            "lead_id": row.lead_id,
            "channel": row.channel,
            "delivery_status": row.delivery_status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "text_preview": (row.text_content or "")[:120],
        }
        for row in recent_inbound_rows
    ]

    outbound_rows = session.exec(
        outbound_query.order_by(UnifiedMessage.id.desc()).limit(60)
    ).all()
    recent_outbound_from_inbound: List[Dict[str, Any]] = [
        {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "thread_id": row.thread_id,
            "lead_id": row.lead_id,
            "delivery_status": row.delivery_status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "source": row.raw_payload.get("source") if isinstance(row.raw_payload, dict) else None,
            "inbound_message_id": (
                row.raw_payload.get("inbound_message_id")
                if isinstance(row.raw_payload, dict)
                else None
            ),
            "text_preview": (row.text_content or "")[:120],
        }
        for row in outbound_rows
        if isinstance(row.raw_payload, dict) and row.raw_payload.get("inbound_message_id") is not None
    ][:30]

    queue_rows = session.exec(
        queue_query.order_by(OutboundQueue.id.desc()).limit(30)
    ).all()
    queue_snapshot: List[Dict[str, Any]] = [
        {
            "id": q.id,
            "tenant_id": q.tenant_id,
            "message_id": q.message_id,
            "channel": q.channel,
            "status": q.status,
            "retry_count": q.retry_count,
            "next_attempt_at": q.next_attempt_at.isoformat() if q.next_attempt_at else None,
            "last_error": q.last_error,
            "updated_at": q.updated_at.isoformat() if q.updated_at else None,
        }
        for q in queue_rows
    ]

    stuck_cutoff = datetime.utcnow().timestamp() - (5 * 60)
    stuck_received_over_5m = len(
        [
            row for row in recent_inbound_rows
            if row.delivery_status == "received"
            and row.created_at is not None
            and row.created_at.timestamp() < stuck_cutoff
        ]
    )

    return {
        "scope_tenant_id": tenant_id,
        "worker_state": get_inbound_worker_debug_snapshot(),
        "summary": {
            "recent_inbound_count": len(recent_inbound_rows),
            "recent_outbound_from_inbound_count": len(recent_outbound_from_inbound),
            "queue_rows_count": len(queue_rows),
            "stuck_received_over_5m_in_recent_window": stuck_received_over_5m,
        },
        "recent_inbound": recent_inbound,
        "recent_outbound_from_inbound": recent_outbound_from_inbound,
        "queue_snapshot": queue_snapshot,
    }

