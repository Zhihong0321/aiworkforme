"""
MODULE: Application Background Tasks
PURPOSE: Execution loops for CRM automation and maintenance logic.
"""
import logging

logger = logging.getLogger(__name__)

async def background_crm_loop():
    """Legacy CRM loop is intentionally disabled in favor of unified messaging workers."""
    logger.info("Starting REAL CRM Background Loop...")
    logger.warning(
        "Legacy CRM loop writes to deprecated tables (legacy_conversation_threads/legacy_chat_messages) "
        "and is disabled until unified messaging workers are implemented."
    )
    return
