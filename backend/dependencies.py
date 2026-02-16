import os
import logging
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from audit import record_security_event
from database import get_session
from mcp_manager import MCPManager
from models import Role, Tenant, TenantMembership, TenantStatus, User
from security import TokenError, decode_access_token
from zai_client import ZaiClient

# Singleton instances
mcp_manager = MCPManager()
zai_client = ZaiClient(api_key=os.getenv("ZAI_API_KEY"))
bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)

def get_mcp_manager() -> MCPManager:
    return mcp_manager

def get_zai_client() -> ZaiClient:
    return zai_client


@dataclass
class AuthContext:
    user: User
    tenant: Optional[Tenant]
    tenant_role: Optional[Role]
    is_platform_admin: bool


def _log_security_denial(
    session: Session,
    request: Optional[Request],
    reason: str,
    status_code: int,
    actor_user_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    endpoint = request.url.path if request else "unknown"
    method = request.method if request else "UNKNOWN"
    try:
        record_security_event(
            session=session,
            actor_user_id=actor_user_id,
            tenant_id=tenant_id,
            event_type="access.denied",
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            reason=reason,
            metadata=metadata or {},
        )
    except Exception:
        # Auth paths must not fail-closed due to telemetry write errors.
        session.rollback()
        logger.exception("Failed to persist security denial event")


def get_auth_context(
    request: Request,
    session: Session = Depends(get_session),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    tenant_header: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
) -> AuthContext:
    if credentials is None:
        _log_security_denial(
            session=session,
            request=request,
            reason="missing_credentials",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError as exc:
        _log_security_denial(
            session=session,
            request=request,
            reason="invalid_token",
            status_code=status.HTTP_401_UNAUTHORIZED,
            metadata={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(exc)}",
        ) from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, int):
        _log_security_denial(
            session=session,
            request=request,
            reason="invalid_token_subject",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        )

    user = session.get(User, user_id)
    if not user or not user.is_active:
        _log_security_denial(
            session=session,
            request=request,
            reason="inactive_or_missing_user",
            status_code=status.HTTP_401_UNAUTHORIZED,
            actor_user_id=user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    is_platform_admin = bool(user.is_platform_admin)
    tenant_id_from_token = payload.get("tenant_id")
    selected_tenant_id: Optional[int] = None

    if tenant_header is not None:
        try:
            selected_tenant_id = int(tenant_header)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Tenant-Id must be an integer",
            ) from exc
    elif isinstance(tenant_id_from_token, int):
        selected_tenant_id = tenant_id_from_token

    tenant: Optional[Tenant] = None
    tenant_role: Optional[Role] = None
    if selected_tenant_id is not None:
        tenant = session.get(Tenant, selected_tenant_id)
        if not tenant or tenant.status != TenantStatus.ACTIVE:
            _log_security_denial(
                session=session,
                request=request,
                reason="tenant_unavailable",
                status_code=status.HTTP_403_FORBIDDEN,
                actor_user_id=user.id,
                tenant_id=selected_tenant_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant is not available",
            )

        membership = session.exec(
            select(TenantMembership).where(
                TenantMembership.user_id == user.id,
                TenantMembership.tenant_id == selected_tenant_id,
                TenantMembership.is_active == True,
            )
        ).first()

        if membership:
            tenant_role = membership.role
        elif not is_platform_admin:
            _log_security_denial(
                session=session,
                request=request,
                reason="tenant_membership_required",
                status_code=status.HTTP_403_FORBIDDEN,
                actor_user_id=user.id,
                tenant_id=selected_tenant_id,
                metadata={"requested_tenant_id": selected_tenant_id},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not belong to this tenant",
            )

    return AuthContext(
        user=user,
        tenant=tenant,
        tenant_role=tenant_role,
        is_platform_admin=is_platform_admin,
    )


def require_authenticated_user(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    return context


def require_tenant_access(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if context.tenant is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context is required. Provide X-Tenant-Id or login with tenant_id.",
        )

    if context.is_platform_admin:
        return context

    if context.tenant_role not in (Role.TENANT_ADMIN, Role.TENANT_USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant role is required",
        )
    return context


def require_platform_admin(
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
) -> AuthContext:
    if not context.is_platform_admin:
        _log_security_denial(
            session=session,
            request=request,
            reason="platform_admin_required",
            status_code=status.HTTP_403_FORBIDDEN,
            actor_user_id=context.user.id,
            tenant_id=context.tenant.id if context.tenant else None,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin role required",
        )
    return context
