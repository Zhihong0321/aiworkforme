"""
MODULE: Database Adapter - Audit Recorder
PURPOSE: Helper functions to record audit and security events in the database.
"""
import logging
from typing import Optional, Dict, Any
from sqlmodel import Session
from src.adapters.db.audit_models import AdminAuditLog, SecurityEventLog

logger = logging.getLogger(__name__)

def record_admin_audit(
    session: Session,
    actor_user_id: int,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    tenant_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Records an administrative action to the audit log."""
    try:
        log = AdminAuditLog(
            actor_user_id=actor_user_id,
            tenant_id=tenant_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=metadata or {},
        )
        session.add(log)
        session.commit()
    except Exception as e:
        logger.error(f"Failed to record admin audit: {e}")
        session.rollback()

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
    """Records a security-related event (e.g., login failure, access denied)."""
    try:
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
    except Exception as e:
        logger.error(f"Failed to record security event: {e}")
        session.rollback()
