"""
MODULE: Platform Router Composition
PURPOSE: Compose platform admin subrouters under one stable API prefix.
DOES: Aggregate focused route modules into a single APIRouter export.
DOES NOT: Contain endpoint business logic directly.
INVARIANTS: Prefix/tag must remain stable for backwards compatibility.
SAFE CHANGE: Add/remove subrouters when moving route implementations.
"""

from fastapi import APIRouter

from . import (
    platform_audit_routes,
    platform_identity_routes,
    platform_llm_routes,
    platform_settings_routes,
)

router = APIRouter(prefix="/api/v1/platform", tags=["Platform Admin"])
router.include_router(platform_identity_routes.router)
router.include_router(platform_audit_routes.router)
router.include_router(platform_llm_routes.router)
router.include_router(platform_settings_routes.router)
