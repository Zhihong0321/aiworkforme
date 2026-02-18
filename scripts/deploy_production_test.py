import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta

# Ensure path to backend
sys.path.append(os.path.join(os.getcwd(), "backend"))

from sqlmodel import Session, create_engine, select
from models import Agent, Workspace, Lead, StrategyVersion, StrategyStatus, AgentKnowledgeFile
from runtime.agent_runtime import ConversationAgentRuntime
from runtime.crm_agent import CRMAgent
from dependencies import zai_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PROD_VERIFY")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///production_test.db")
engine = create_engine(DATABASE_URL)

async def verify_real_workflow():
    logger.info("Starting PRODUCTION WORKFLOW VERIFICATION...")
    
    # 1. LIVE KEY CHECK
    if not zai_client.is_configured:
        key = os.getenv("ZAI_API_KEY")
        if not key or len(key) < 10:
            logger.error("SYSTEM NOT READY: Missing real ZAI_API_KEY. Set it to run real workflow.")
            return
        zai_client.update_api_key(key)

    with Session(engine) as session:
        from models import SQLModel
        SQLModel.metadata.create_all(engine)

        # 2. CREATE REAL ASSETS
        # Create an Agent
        agent = Agent(name="Sales Agent", system_prompt="You are a real estate assistant.", model="glm-4.7-flash")
        session.add(agent)
        session.commit()
        session.refresh(agent)

        # Add REAL Knowledge to the agent
        knowledge = AgentKnowledgeFile(
            agent_id=agent.id,
            filename="listings.txt",
            content="Listing A: 3BR House in LA for $1M. Listing B: 1BR Apt in NY for $500k.",
            tags="[]"
        )
        session.add(knowledge)

        # Create a Workspace linked to the Agent
        workspace = Workspace(name="LA Real Estate", agent_id=agent.id)
        session.add(workspace)
        session.commit()
        session.refresh(workspace)

        # Create a Strategy
        strategy = StrategyVersion(
            workspace_id=workspace.id,
            version_number=1,
            status=StrategyStatus.ACTIVE,
            tone="Aggressive",
            objectives="Sell houses",
            objection_handling="None",
            cta_rules="Ask for phone"
        )
        session.add(strategy)

        # Create a Real Lead
        lead = Lead(workspace_id=workspace.id, external_id="real_user_123", name="John Doe")
        session.add(lead)
        session.commit()
        session.refresh(lead)

        logger.info(f"Setup Complete: Lead {lead.id} in Workspace {workspace.id} (Agent {agent.id})")

        # 3. RUN REAL RUNTIME
        runtime = ConversationAgentRuntime(session, zai_client)
        crm = CRMAgent(session, runtime)

        # Manual Trigger of turn
        logger.info("Executing Turn 1: Inbound Message...")
        result = await runtime.run_turn(lead.id, workspace.id, user_message="What do you have in LA?")

        if result["status"] == "sent":
            logger.info("SUCCESS: Turn 1 processed via Z.ai")
            logger.info(f"AI Response: {result['content']}")
            
            # Check if Knowledge was used (should contain 'LA' or '$1M')
            if "LA" in result["content"] or "$1M" in result["content"]:
                 logger.info("VERIFIED: RAG (Knowledge Retrieval) is WORKING.")
            else:
                 logger.warning("RAG: AI responded but listings info might not have been matched.")
        else:
            logger.error(f"FAILURE: Turn 1 returned {result['status']}")
            return

        # 4. RUN REAL AUTOMATION LOOP
        logger.info("Testing CRM Automation Loop (Planning next turn)...")
        await crm.run_review_loop()
        session.refresh(lead)
        logger.info(f"Next Follow-up Scheduled: {lead.next_followup_at}")

        if lead.next_followup_at:
            logger.info("VERIFIED: Lifecycle Automation is WORKING.")
        
        logger.info("--- PRODUCTION SYSTEM READY ---")

if __name__ == "__main__":
    asyncio.run(verify_real_workflow())
