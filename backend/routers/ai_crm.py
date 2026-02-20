"""
MODULE: AI CRM Router Composition
PURPOSE: Compose AI CRM route handlers under a stable workspaces prefix.
DOES: Aggregate AI CRM route modules and re-export background-cycle entrypoint.
DOES NOT: Implement endpoint business logic directly.
INVARIANTS: Prefix/tag and background-cycle export name remain stable.
SAFE CHANGE: Add/remove subrouters when route logic is moved.
"""

from fastapi import APIRouter

from . import ai_crm_routes
from .ai_crm_runtime import run_ai_crm_background_cycle

router = APIRouter(prefix="/api/v1/workspaces", tags=["AI CRM"])
router.include_router(ai_crm_routes.router)


def get_default_ai_crm_llm_router():
    """Provide the default shared LLM router used by AI CRM background loop."""
    from src.adapters.api.dependencies import llm_router

    return llm_router

__all__ = ["router", "run_ai_crm_background_cycle", "get_default_ai_crm_llm_router"]
