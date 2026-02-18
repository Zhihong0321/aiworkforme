"""
MODULE: API Dependencies
PURPOSE: FastAPI dependency functions for authentication and injection.
"""
import os
import logging
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

# Internal Imports (Refactored paths)
from src.adapters.db.audit_models import SecurityEventLog
from src.adapters.db.user_models import User, TenantMembership
from src.adapters.db.tenant_models import Tenant
from src.domain.entities.enums import Role, TenantStatus
from src.adapters.mcp.manager import MCPManager
from src.infra.llm.schemas import LLMTask
from src.infra.llm.router import LLMRouter
from src.infra.llm.providers.zai import ZaiProvider
from src.infra.llm.providers.uniapi import UniAPIProvider
from src.infra.database import get_session
from src.infra.security import TokenError, decode_access_token

# Singletons (Ideally managed by DI, but kept as is for safe refactor)
mcp_manager = MCPManager()

# Initialize Providers
zai_provider = ZaiProvider(api_key=os.getenv("ZAI_API_KEY"))
uniapi_provider = UniAPIProvider(api_key=os.getenv("UNIAPI_API_KEY"))

# Initialize Global Router
llm_router = LLMRouter(
    providers={
        "zai": zai_provider,
        "uniapi": uniapi_provider
    },
    routing_config={
        LLMTask.CONVERSATION: "zai",
        LLMTask.EXTRACTION: "uniapi",  # Gemini is better for extraction
        LLMTask.TOOL_USE: "zai"
    }
)

bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)

@dataclass
class AuthContext:
    user: User
    tenant: Optional[Tenant]
    tenant_role: Optional[Role]
    is_platform_admin: bool

def get_auth_context(
    request: Request,
    session: Session = Depends(get_session),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    tenant_header: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
) -> AuthContext:
    if credentials is None:
        _log_security_denial(session, request, "missing_credentials", 401)
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError as exc:
        _log_security_denial(session, request, "invalid_token", 401, metadata={"error": str(exc)})
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(exc)}") from exc

    sub = payload.get("sub")
    try:
        user_id = int(sub) if sub is not None else None
    except (ValueError, TypeError):
        user_id = None

    if user_id is None:
        _log_security_denial(session, request, "invalid_token_subject", 401)
        raise HTTPException(status_code=401, detail="Invalid token subject")

    user = session.get(User, user_id)
    if not user or not user.is_active:
        _log_security_denial(session, request, "inactive_or_missing_user", 401, actor_user_id=user_id)
        raise HTTPException(status_code=401, detail="User not found or inactive")

    is_platform_admin = bool(user.is_platform_admin)
    tenant_id_from_token = payload.get("tenant_id")
    selected_tenant_id: Optional[int] = None

    if tenant_header is not None:
        try: selected_tenant_id = int(tenant_header)
        except ValueError: raise HTTPException(status_code=400, detail="X-Tenant-Id must be an integer")
    elif isinstance(tenant_id_from_token, int):
        selected_tenant_id = tenant_id_from_token

    tenant: Optional[Tenant] = None
    tenant_role: Optional[Role] = None
    if selected_tenant_id is not None:
        tenant = session.get(Tenant, selected_tenant_id)
        if not tenant or tenant.status != TenantStatus.ACTIVE:
            _log_security_denial(session, request, "tenant_unavailable", 403, user.id, selected_tenant_id)
            raise HTTPException(status_code=403, detail="Tenant is not available")

        membership = session.exec(
            select(TenantMembership).where(
                TenantMembership.user_id == user.id,
                TenantMembership.tenant_id == selected_tenant_id,
                TenantMembership.is_active == True,
            )
        ).first()

        if membership: tenant_role = membership.role
        elif not is_platform_admin:
            _log_security_denial(session, request, "tenant_membership_required", 403, user.id, selected_tenant_id)
            raise HTTPException(status_code=403, detail="User does not belong to this tenant")

    return AuthContext(user=user, tenant=tenant, tenant_role=tenant_role, is_platform_admin=is_platform_admin)

def _log_security_denial(session, request, reason, status_code, actor_user_id=None, tenant_id=None, metadata=None):
    # Proxy to audit.py recorder
    from src.adapters.db.audit_recorder import record_security_event
    endpoint = request.url.path if request else "unknown"
    method = request.method if request else "UNKNOWN"
    try:
        record_security_event(
            session=session, actor_user_id=actor_user_id, tenant_id=tenant_id,
            event_type="access.denied", endpoint=endpoint, method=method,
            status_code=status_code, reason=reason, metadata=metadata or {},
        )
    except Exception:
        session.rollback()
        logger.exception("Failed to persist security denial event")

def require_authenticated_user(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    return context

def require_tenant_access(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if context.tenant is None:
        raise HTTPException(status_code=400, detail="Tenant context is required")
    if context.is_platform_admin: return context
    if context.tenant_role not in (Role.TENANT_ADMIN, Role.TENANT_USER):
        raise HTTPException(status_code=403, detail="Tenant access required")
    return context

def require_platform_admin(request: Request, context: AuthContext = Depends(get_auth_context), session: Session = Depends(get_session)) -> AuthContext:
    if not context.is_platform_admin:
        _log_security_denial(session, request, "platform_admin_required", 403, context.user.id, context.tenant.id if context.tenant else None)
        raise HTTPException(status_code=403, detail="Platform admin role required")
    return context

def get_mcp_manager() -> MCPManager:
    return mcp_manager

def get_llm_router() -> LLMRouter:
    return llm_router

def refresh_llm_router_config(session: Session):
    """
    Reloads the LLM routing configuration from the database.
    """
    from src.adapters.db.tenant_models import SystemSetting
    setting = session.get(SystemSetting, "llm_routing_config")
    if setting and setting.value:
        try:
            import json
            raw_config = json.loads(setting.value)
            # Map string keys to LLMTask enum
            new_config = {LLMTask(k): v for k, v in raw_config.items()}
            llm_router.update_routing_config(new_config)
        except Exception as e:
            logger.error(f"Failed to refresh LLM routing config: {e}")

# Deprecated: Kept for temporary backward compatibility during refactor
def get_zai_client():
    from src.adapters.zai.client import ZaiClient
    return ZaiClient(api_key=os.getenv("ZAI_API_KEY"))
