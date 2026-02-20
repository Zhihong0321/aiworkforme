"""
MODULE: API Router Registry
PURPOSE: Single place to attach all HTTP routers to FastAPI app.
DOES: Registers routers and tenant/platform dependency wrappers.
DOES NOT: Implement endpoint logic or startup behavior.
INVARIANTS: Route prefixes and dependency scopes must remain stable.
SAFE CHANGE: Add/remove router includes only when endpoints move.
"""

from fastapi import Depends, FastAPI

from routers import (
    agents,
    ai_crm,
    analytics,
    auth,
    calendar,
    catalog,
    chat,
    debug,
    knowledge,
    mcp,
    messaging,
    platform,
    playground,
    policy,
    settings,
    workspaces,
)
from src.adapters.api.dependencies import require_platform_admin, require_tenant_access


def register_api_routers(app: FastAPI) -> None:
    """Attach all API routers with their auth scope dependencies."""
    app.include_router(auth.router)
    app.include_router(platform.router, dependencies=[Depends(require_platform_admin)])

    tenant_dependencies = [Depends(require_tenant_access)]
    app.include_router(mcp.router, dependencies=tenant_dependencies)
    app.include_router(chat.router, dependencies=tenant_dependencies)
    app.include_router(agents.router, dependencies=tenant_dependencies)
    app.include_router(knowledge.router, dependencies=tenant_dependencies)
    app.include_router(policy.router, dependencies=tenant_dependencies)
    app.include_router(playground.router, dependencies=tenant_dependencies)
    app.include_router(workspaces.router, dependencies=tenant_dependencies)
    app.include_router(catalog.router, dependencies=tenant_dependencies)
    app.include_router(analytics.router, dependencies=tenant_dependencies)
    app.include_router(calendar.router, dependencies=tenant_dependencies)
    app.include_router(messaging.router, dependencies=tenant_dependencies)
    app.include_router(ai_crm.router, dependencies=tenant_dependencies)

    app.include_router(settings.router, dependencies=[Depends(require_platform_admin)])
    app.include_router(debug.router)
