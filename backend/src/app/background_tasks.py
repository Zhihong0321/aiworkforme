"""
MODULE: Application Background Tasks
PURPOSE: Execution loops for CRM automation and maintenance logic.
"""
import asyncio
import logging
from sqlmodel import Session
from src.infra.database import engine
from src.adapters.api.dependencies import llm_router
from src.app.runtime.agent_runtime import ConversationAgentRuntime
from src.app.runtime.crm_agent import CRMAgent

logger = logging.getLogger(__name__)

async def background_crm_loop():
    """Real Automation Heartbeat: Runs Review and Dispatch loops."""
    logger.info("Starting REAL CRM Background Loop...")
    logger.warning(
        "Legacy CRM loop writes to deprecated tables (et_conversation_threads/et_chat_messages) "
        "and is disabled until unified messaging workers are implemented."
    )
    return
    while True:
        try:
            with Session(engine) as session:
                runtime = ConversationAgentRuntime(session, llm_router)
                crm = CRMAgent(session, runtime)
                
                # 1. Review Loop: Plan follow-ups for new/neglected leads
                await crm.run_review_loop()
                
                # 2. Dispatcher: Execute turns for leads that are 'due'
                await crm.run_due_dispatcher()
                
        except Exception as e:
            logger.error(f"CRM Loop Error: {e}")
        
        # Interval for MVP: Check every 60 seconds
        await asyncio.sleep(60)
