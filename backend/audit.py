from typing import Any, Dict, Optional

from sqlmodel import Session

from models import AdminAuditLog, SecurityEventLog


def record_admin_audit(
    session: Session,
    actor_user_id: int,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    tenant_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    event = AdminAuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        tenant_id=tenant_id,
        details=metadata or {},
    )
    session.add(event)
    session.commit()


def record_security_event(
    session: Session,
    event_type: str,
    endpoint: str,
    method: str,
    status_code: int,
    reason: str,
    actor_user_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    event = SecurityEventLog(
        actor_user_id=actor_user_id,
        tenant_id=tenant_id,
        event_type=event_type,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        reason=reason,
        details=metadata or {},
    )
    session.add(event)
    session.commit()
