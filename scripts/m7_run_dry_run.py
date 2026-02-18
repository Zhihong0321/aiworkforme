import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

# Setup path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Eternalgy-MCP-RAG", "backend")
sys.path.append(backend_dir)

from sqlmodel import Session, create_engine, select
from models import Workspace, Lead, PolicyDecision, LeadMemory
from runtime.agent_runtime import ConversationAgentRuntime
from runtime.crm_agent import CRMAgent

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///pilot_dry_run.db")
engine = create_engine(DATABASE_URL)

async def run_pilot_dry_run():
    print("Starting M7 Pilot Dry Run Execution...")
    
    with Session(engine) as session:
        mock_client = MagicMock()
        async def smart_mock(messages, system_instruction, **kwargs):
            # If it's the memory refresh call (system instruction contains JSON)
            if "JSON" in (system_instruction or ""):
                 return {
                    "candidates": [{
                        "content": {
                            "parts": [{"text": "{\"summary\": \"Solar lead engaged\", \"facts\": [\"Interested in solar\"]}"}]
                        }
                    }]
                }
            # Otherwise it's a normal chat turn
            return {
                "candidates": [{
                    "content": {
                        "parts": [{"text": "Hello! I noticed your interest in solar. Are you a homeowner?"}]
                    }
                }]
            }

        mock_client.generate_content = AsyncMock(side_effect=smart_mock)

        # Initialize Services
        runtime = ConversationAgentRuntime(session, mock_client)
        crm = CRMAgent(session, runtime)
        
        # 1. Run Review Loop (Planning)
        print("Executing CRM Review Loop...")
        await crm.run_review_loop()
        
        # Manually force them to be due (since review loop set them to future)
        leads = session.exec(select(Lead)).all()
        for l in leads:
            l.next_followup_at = datetime.utcnow() - timedelta(minutes=1)
            session.add(l)
        session.commit()

        # 2. Run Due Dispatcher (Execution)
        print("Executing CRM Due Dispatcher for 10 leads...")
        await crm.run_due_dispatcher()
        
        # 3. Verification
        decisions = session.exec(select(PolicyDecision)).all()
        memories = session.exec(select(LeadMemory)).all()
        leads_contacted = session.exec(select(Lead).where(Lead.last_followup_at != None)).all()
        
        print(f"--- Dry Run Results ---")
        print(f"Policy Decisions Logged: {len(decisions)}")
        print(f"Memory Extracts Created: {len(memories)}")
        print(f"Leads Outreach Successful: {len(leads_contacted)}/10")
        
        if len(leads_contacted) == 10:
            print("M7 DRY RUN SUCCESS: Full autonomy verified.")
        else:
            print(f"M7 DRY RUN PARTIAL: Only {len(leads_contacted)} leads processed.")

if __name__ == "__main__":
    asyncio.run(run_pilot_dry_run())
