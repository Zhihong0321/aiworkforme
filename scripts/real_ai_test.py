import sys
import os
import asyncio
import logging
from datetime import datetime

# Setup path to root backend
sys.path.append(os.path.join(os.getcwd(), "backend"))

from sqlmodel import Session, create_engine, select
from models import Workspace, Lead, StrategyVersion, StrategyStatus, BudgetTier, FollowUpPreset
from runtime.agent_runtime import ConversationAgentRuntime
from dependencies import zai_client

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RealAITest")

# Use Production DB or Local Fallback
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///test.db")
engine = create_engine(DATABASE_URL)

async def run_real_ai_test():
    logger.info(f"Starting REAL AI Test against: {DATABASE_URL}")
    
    if not zai_client.is_configured:
        # Check if environment variable is available
        key = os.getenv("ZAI_API_KEY")
        if not key:
            logger.error("FAIL: ZAI_API_KEY not found in environment or database.")
            return
        zai_client.update_api_key(key)

    with Session(engine) as session:
        # 1. Ensure a Workspace exists
        workspace = session.exec(select(Workspace)).first()
        if not workspace:
            logger.info("Seeding test workspace...")
            workspace = Workspace(name="Real Test Corp", timezone="UTC", budget_tier=BudgetTier.GREEN)
            session.add(workspace)
            session.commit()
            session.refresh(workspace)

        # 2. Ensure an Active Strategy exists
        strategy = session.exec(select(StrategyVersion).where(StrategyVersion.workspace_id == workspace.id)).first()
        if not strategy:
            logger.info("Seeding test strategy...")
            strategy = StrategyVersion(
                workspace_id=workspace.id,
                version_number=1,
                status=StrategyStatus.ACTIVE,
                tone="Professional",
                objectives="Test the system",
                objection_handling="Be nice",
                cta_rules="Always end with a question",
                followup_preset=FollowUpPreset.BALANCED
            )
            session.add(strategy)
            session.commit()

        # 3. Create a clean Test Lead
        lead_id_ext = f"test_{int(datetime.utcnow().timestamp())}"
        test_lead = Lead(
            workspace_id=workspace.id,
            external_id=lead_id_ext,
            name="Real AI Tester",
            timezone="UTC"
        )
        session.add(test_lead)
        session.commit()
        session.refresh(test_lead)

        logger.info(f"Created Real Test Lead: ID {test_lead.id}")

        # 4. EXECUTE PRODUCTION RUNTIME (NO MOCKS)
        runtime = ConversationAgentRuntime(session, zai_client)
        
        logger.info("Executing REAL AI turn (this makes an actual API call)...")
        result = await runtime.run_turn(
            lead_id=test_lead.id, 
            workspace_id=workspace.id, 
            user_message="Hi, I am interested in your services. Can you tell me more?"
        )

        # 5. VERIFICATION
        if result["status"] == "sent":
            logger.info("PASS: AI successfully generated and saved a response.")
            logger.info(f"AI Said: {result['content']}")
        else:
            logger.error(f"FAIL: Turn failed with status: {result['status']}. Reason: {result.get('reason')}")

if __name__ == "__main__":
    from models import SQLModel
    SQLModel.metadata.create_all(engine)
    asyncio.run(run_real_ai_test())
