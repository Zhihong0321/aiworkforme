"""
MODULE: API Dependencies
PURPOSE: FastAPI dependency functions for authentication and injection.
"""
import importlib
import logging
from dataclasses import dataclass
from typing import Any, Optional, Dict

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

# Internal Imports (Refactored paths)
from src.adapters.db.audit_models import SecurityEventLog
from src.adapters.db.user_models import User, TenantMembership
from src.adapters.db.tenant_models import Tenant, SystemSetting
from src.adapters.mcp.manager import MCPManager

Role = importlib.import_module("src.domain.entities.enums").Role
TenantStatus = importlib.import_module("src.domain.entities.enums").TenantStatus
LLMTask = importlib.import_module("src.infra.llm.schemas").LLMTask
LLMRouter = importlib.import_module("src.infra.llm.router").LLMRouter
ZaiProvider = importlib.import_module("src.infra.llm.providers.zai").ZaiProvider
UniAPIProvider = importlib.import_module("src.infra.llm.providers.uniapi").UniAPIProvider
get_session = importlib.import_module("src.infra.database").get_session
TokenError = importlib.import_module("src.infra.security").TokenError
decode_access_token = importlib.import_module("src.infra.security").decode_access_token

# Singletons (Ideally managed by DI, but kept as is for safe refactor)
mcp_manager = MCPManager()

# Initialize Providers (API keys are loaded from Platform Admin settings at startup/runtime)
zai_provider = ZaiProvider(api_key=None)
uniapi_provider = UniAPIProvider(api_key=None)

# Initialize Global Router
llm_router = LLMRouter(
    providers={
        "zai": zai_provider,
        "uniapi": uniapi_provider
    },
    routing_config={
        LLMTask.CONVERSATION: "uniapi",
        LLMTask.EXTRACTION: "uniapi",
        LLMTask.REASONING: "uniapi",
        LLMTask.TOOL_USE: "uniapi",
        LLMTask.AI_CRM: "uniapi",
    },
    task_model_config={},
    default_provider="uniapi",
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


def refresh_provider_keys_from_db(session: Session) -> None:
    zai_setting = session.get(SystemSetting, "zai_api_key")
    uni_setting = session.get(SystemSetting, "uniapi_key")

    zai_provider.set_api_key(zai_setting.value if zai_setting and zai_setting.value else "")
    uniapi_provider.set_api_key(uni_setting.value if uni_setting and uni_setting.value else "")


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


def refresh_llm_task_model_config(session: Session):
    """
    Reloads per-task default model mapping from DB.
    """
    setting = session.get(SystemSetting, "llm_task_model_config")
    if setting and setting.value:
        try:
            import json
            raw_config = json.loads(setting.value)
            valid_tasks = {t.value for t in LLMTask}
            sanitized: Dict[LLMTask, Optional[str]] = {}
            for task_key, model_name in raw_config.items():
                if task_key not in valid_tasks:
                    continue
                model = (str(model_name).strip() if model_name is not None else "")
                sanitized[LLMTask(task_key)] = model or None
            llm_router.update_task_model_config(sanitized)
        except Exception as e:
            logger.error(f"Failed to refresh LLM task model config: {e}")
            llm_router.update_task_model_config({})
    else:
        llm_router.update_task_model_config({})

# Deprecated: Kept for temporary backward compatibility during refactor
def get_zai_client(session: Session = Depends(get_session)):
    from src.adapters.zai.client import ZaiClient
    setting = session.get(SystemSetting, "zai_api_key")
    key = setting.value if setting and setting.value else ""
    return ZaiClient(api_key=key)
