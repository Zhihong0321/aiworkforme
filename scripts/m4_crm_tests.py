import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

# Setup path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Eternalgy-MCP-RAG", "backend")
sys.path.append(backend_dir)

from sqlmodel import Session, SQLModel, create_engine, select
from models import Lead, Workspace, StrategyVersion, StrategyStatus, LeadStage, FollowUpPreset
from runtime.crm_agent import CRMAgent
from runtime.agent_runtime import ConversationAgentRuntime

# Use a test SQLite DB
import logging
logging.basicConfig(level=logging.INFO)
TEST_DB_URL = "sqlite:///crm_test.db"
engine = create_engine(TEST_DB_URL)

async def test_crm_loops():
    print("Starting M4 CRM Loop Tests...")
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # 1. Setup Data
        ws = Workspace(id=1, name="CRM Test WS")
        strategy = StrategyVersion(
            workspace_id=ws.id, 
            version_number=1, 
            status=StrategyStatus.ACTIVE,
            tone="Professional",
            objectives="Followup",
            objection_handling="none",
            cta_rules="none",
            followup_preset=FollowUpPreset.AGGRESSIVE # 24h
        )
        
        # Lead due for review
        lead_to_review = Lead(id=1, workspace_id=ws.id, external_id="w:1", last_followup_review_at=None)
        # Lead due for dispatch - set review_at to now so review loop skips it
        lead_due = Lead(id=2, workspace_id=ws.id, external_id="w:2", 
                        last_followup_review_at=datetime.utcnow(),
                        next_followup_at=datetime.utcnow() - timedelta(minutes=5))
        
        session.add(ws)
        session.add(strategy)
        session.add(lead_to_review)
        session.add(lead_due)
        session.commit()

        # 2. Mock Runtime
        mock_runtime = MagicMock()
        mock_runtime.run_turn = AsyncMock(return_value={"status": "sent", "content": "Ping!"})

        crm = CRMAgent(session, mock_runtime)

        # 3. Test: Review Loop
        print("Test Case: Review Loop identifies needing-review leads...")
        await crm.run_review_loop()
        session.refresh(lead_to_review)
        assert lead_to_review.last_followup_review_at is not None
        assert lead_to_review.next_followup_at is not None
        # Aggressive preset = 24h
        expected_next = datetime.utcnow() + timedelta(hours=24)
        assert abs((lead_to_review.next_followup_at - expected_next).total_seconds()) < 60
        print("PASS: Review Loop Planning")

        # 4. Test: Due Dispatcher
        print("Test Case: Due Dispatcher triggers runtime...")
        all_leads = session.exec(select(Lead)).all()
        for l in all_leads:
            print(f"DEBUG: Lead id={l.id} stage='{l.stage}' type={type(l.stage)} next='{l.next_followup_at}'")
        
        await crm.run_due_dispatcher()
        # Verify mock was called for lead_due
        # Based on my implementation, it iterates through session objects. 
        # lead_due.id is 2.
        mock_runtime.run_turn.assert_called()
        print("PASS: Due Dispatcher Execution")

        # 5. Test: State Transition
        print("Test Case: State Transition Logic...")
        crm.transition_state(lead_due.id, new_stage=LeadStage.QUALIFIED, add_tags=["POSITIVE"])
        session.refresh(lead_due)
        assert lead_due.stage == LeadStage.QUALIFIED
        assert "POSITIVE" in lead_due.tags
        print("PASS: Manual State Transition")

    print("M4 CRM Loop Tests Completed.")

if __name__ == "__main__":
    asyncio.run(test_crm_loops())
