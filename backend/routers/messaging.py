"""
MODULE: Messaging Router Composition
PURPOSE: Compose unified messaging subrouters under a stable API prefix.
DOES: Aggregate focused messaging route modules into one exported router.
DOES NOT: Implement route business logic directly.
INVARIANTS: Prefix and tags remain stable for backwards compatibility.
SAFE CHANGE: Add/remove subrouters when endpoints are moved.
"""

from fastapi import APIRouter

from . import (
    messaging_core_routes,
    messaging_mvp_routes,
    messaging_whatsapp_import_routes,
    messaging_whatsapp_routes,
)
from .messaging_runtime import dispatch_next_outbound_for_tenant, list_tenant_ids_with_queued_outbound

router = APIRouter(prefix="/api/v1/messaging", tags=["Unified Messaging"])
router.include_router(messaging_whatsapp_routes.router)
router.include_router(messaging_whatsapp_import_routes.router)
router.include_router(messaging_core_routes.router)
router.include_router(messaging_mvp_routes.router)

__all__ = [
    "router",
    "dispatch_next_outbound_for_tenant",
    "list_tenant_ids_with_queued_outbound",
]
