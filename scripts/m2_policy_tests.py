import sys
import os
from datetime import datetime, timedelta
import pytz

# Setup path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Eternalgy-MCP-RAG", "backend")
sys.path.append(backend_dir)

from sqlmodel import Session, SQLModel, create_engine
from models import Lead, Workspace, LeadStage, LeadTag, ConversationThread, ChatMessageNew
from policy.evaluator import PolicyEvaluator

# Use a test SQLite DB
TEST_DB_URL = "sqlite:///policy_test.db"
engine = create_engine(TEST_DB_URL)

def run_policy_tests():
    print("Starting M2 Policy Engine Tests...")
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # --- Preparation ---
        ws = Workspace(name="Test WS", timezone="America/New_York")
        session.add(ws)
        session.commit()
        session.refresh(ws)

        # 1. Test: Outbound Cap (24h)
        lead1 = Lead(workspace_id=ws.id, external_id="123", last_followup_at=datetime.utcnow() - timedelta(hours=5))
        session.add(lead1)
        session.commit()
        
        evaluator = PolicyEvaluator(session)
        decision = evaluator.evaluate_outbound(lead1.id, ws.id)
        assert decision.allow_send == False
        assert decision.reason_code == "OUTBOUND_CAP_24H"
        print("PASS: Outbound Cap (24h)")

        # 2. Test: Quiet Hours (9 PM in HK is 8 AM in NY - wait, let's use explicit UTC to control)
        # 3 AM UTC is 10 PM in NY (Night - Block)
        # 15 PM UTC is 10 AM in NY (Day - Allow)
        
        lead_ny = Lead(workspace_id=ws.id, external_id="456", timezone="America/New_York")
        session.add(lead_ny)
        session.commit()

        # We need to mock datetime or time for this test to be deterministic 
        # But for now, we'll check the current local result based on real time
        decision_qh = evaluator.evaluate_outbound(lead_ny.id, ws.id)
        print(f"Quiet Hours Test result: {decision_qh.reason_code} at current local time")

        # 3. Test: Opt-Out
        lead_opt = Lead(workspace_id=ws.id, external_id="789", stage=LeadStage.SUPPRESSED)
        session.add(lead_opt)
        session.commit()
        decision_opt = evaluator.evaluate_outbound(lead_opt.id, ws.id)
        assert decision_opt.allow_send == False
        assert decision_opt.reason_code == "OPT_OUT_SUPPRESSION"
        print("PASS: Opt-Out Suppression")

        # 4. Test: Stop Rule (5 unanswered)
        lead_stop = Lead(workspace_id=ws.id, external_id="999")
        session.add(lead_stop)
        session.commit()
        
        thread = ConversationThread(workspace_id=ws.id, lead_id=lead_stop.id)
        session.add(thread)
        session.commit()
        
        for i in range(5):
            msg = ChatMessageNew(thread_id=thread.id, role="model", content=f"Hello {i}", created_at=datetime.utcnow() - timedelta(minutes=10))
            session.add(msg)
        session.commit()
        
        decision_stop = evaluator.evaluate_outbound(lead_stop.id, ws.id)
        assert decision_stop.allow_send == False
        assert decision_stop.reason_code == "STOP_RULE_MAX_UNANSWERED"
        print("PASS: Stop Rule (5 Unanswered)")

        # 5. Test: Risk Blocking
        decision_risk = evaluator.validate_risk(lead_stop.id, ws.id, "This is not unsolicited spam", 0.5)
        assert decision_risk.allow_send == False
        assert decision_risk.reason_code == "LOW_CONFIDENCE_BLOCK"
        
        # Verify tag was added
        session.refresh(lead_stop)
        assert LeadTag.STRATEGY_REVIEW_REQUIRED in lead_stop.tags
        print("PASS: Risk Blocking (Low Confidence + Tagging)")

    print("M2 Policy Engine Tests Completed.")

if __name__ == "__main__":
    run_policy_tests()
