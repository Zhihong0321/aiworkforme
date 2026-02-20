"""
MODULE: Application Background Tasks - AI CRM
PURPOSE: Periodic conversation scan + due follow-up generation for AI CRM workflow.
"""
import asyncio
import importlib
import logging
import os

from sqlmodel import Session

from routers.ai_crm import get_default_ai_crm_llm_router, run_ai_crm_background_cycle

logger = logging.getLogger(__name__)


AI_CRM_POLL_SECONDS = float(os.getenv("AI_CRM_POLL_SECONDS", "30"))


def _get_engine():
    return importlib.import_module("src.infra.database").engine


async def background_ai_crm_loop():
    logger.info("Starting AI CRM loop (poll=%ss)", AI_CRM_POLL_SECONDS)
    llm_router = get_default_ai_crm_llm_router()
    while True:
        try:
            with Session(_get_engine()) as session:
                stats = await run_ai_crm_background_cycle(session, llm_router)
                if stats.get("scanned") or stats.get("triggered"):
                    logger.info(
                        "AI CRM cycle completed: scanned=%s triggered=%s",
                        stats.get("scanned", 0),
                        stats.get("triggered", 0),
                    )
        except Exception as exc:
            logger.exception("AI CRM loop error: %s", exc)

        await asyncio.sleep(AI_CRM_POLL_SECONDS)
