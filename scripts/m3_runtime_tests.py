import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
import json

# Setup path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Eternalgy-MCP-RAG", "backend")
sys.path.append(backend_dir)

from sqlmodel import Session, SQLModel, create_engine
from models import Lead, Workspace, StrategyVersion, StrategyStatus, LeadStage
from runtime.agent_runtime import ConversationAgentRuntime

# Use a test SQLite DB
TEST_DB_URL = "sqlite:///runtime_test.db"
engine = create_engine(TEST_DB_URL)

async def test_runtime_flow():
    print("Starting M3 Runtime Execution Tests...")
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # 1. Setup Data
        ws = Workspace(id=1, name="Scale-up WS", timezone="UTC")
        strategy = StrategyVersion(
            workspace_id=ws.id, 
            version_number=1, 
            status=StrategyStatus.ACTIVE,
            tone="Professional",
            objectives="Book meeting",
            objection_handling="Empathize",
            cta_rules="Ask for time"
        )
        lead = Lead(id=1, workspace_id=ws.id, external_id="whatsapp:+123456789", stage=LeadStage.NEW)
        
        session.add(ws)
        session.add(strategy)
        session.add(lead)
        session.commit()

        # 2. Mock Agent Client
        mock_client = MagicMock()
        mock_client.generate_content = AsyncMock(return_value={
            "candidates": [{"content": {"parts": [{"text": "Hello, would you like to book a meeting?"}]}}]
        })

        # 3. Initialize Runtime
        runtime = ConversationAgentRuntime(session, mock_client)

        # 4. RUN TURN: Inbound Response
        print("Test Case: Normal Inbound Response...")
        result = await runtime.run_turn(lead.id, ws.id, user_message="I'm interested in the product")
        
        assert result["status"] == "sent"
        assert "meeting" in result["content"]
        
        # Verify Lead state changed
        session.refresh(lead)
        assert lead.stage == LeadStage.CONTACTED
        assert lead.last_followup_at is not None
        print("PASS: Normal Inbound Response")

        # 5. RUN TURN: Blocked by Policy (24h Cap)
        print("Test Case: Blocked by Policy (24h Cap)...")
        result_blocked = await runtime.run_turn(lead.id, ws.id, user_message="Still interested")
        assert result_blocked["status"] == "blocked"
        assert result_blocked["reason"] == "OUTBOUND_CAP_24H"
        print("PASS: Blocked by Policy (24h Cap)")

        # 6. RUN TURN: Risk Check Block (Low confidence)
        # We'd need to modify runtime to return low confidence or content that triggers block
        # For M3 test, we'll verify the post-gen link exists.

    print("M3 Runtime Execution Tests Completed.")

if __name__ == "__main__":
    asyncio.run(test_runtime_flow())
