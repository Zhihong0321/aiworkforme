import sys
import os
from datetime import datetime, timedelta

# Setup path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Eternalgy-MCP-RAG", "backend")
sys.path.append(backend_dir)

from sqlmodel import Session, create_engine, select
from models import Workspace, Lead, StrategyVersion, StrategyStatus, BudgetTier, FollowUpPreset

# Use the standard database URL if possible, or a dedicated pilot DB
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///pilot_dry_run.db")
engine = create_engine(DATABASE_URL)

def seed_pilot_data():
    print(f"Seeding M7 Pilot Data to {DATABASE_URL}...")
    
    with Session(engine) as session:
        # 1. Create Pilot Workspace
        workspace = Workspace(
            name="SolarFlow Solutions Pilot",
            timezone="America/Los_Angeles",
            budget_tier=BudgetTier.GREEN
        )
        session.add(workspace)
        session.commit()
        session.refresh(workspace)
        
        # 2. Create Solar Strategy
        strategy = StrategyVersion(
            workspace_id=workspace.id,
            version_number=1,
            status=StrategyStatus.ACTIVE,
            tone="Professional, informative, and encouraging",
            objectives="Qualify homeowners for solar potential and book a lookup call.",
            objection_handling="If they mention cost, explain tax credits. If they mention roof age, suggest a free inspection.",
            cta_rules="Always end with a question about their current monthly electric bill.",
            followup_preset=FollowUpPreset.BALANCED
        )
        session.add(strategy)
        
        # 3. Seed 10 Test Leads
        for i in range(1, 11):
            lead = Lead(
                workspace_id=workspace.id,
                external_id=f"pilot_lead_{i}",
                name=f"Homeowner {i}",
                timezone="America/Los_Angeles",
                next_followup_at=datetime.utcnow() - timedelta(minutes=i) # Make them all "due"
            )
            session.add(lead)
        
        session.commit()
        print(f"Successfully seeded Workspace (ID: {workspace.id}) and 10 Leads.")

if __name__ == "__main__":
    from models import SQLModel
    SQLModel.metadata.create_all(engine)
    seed_pilot_data()
