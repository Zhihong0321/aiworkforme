import sys
import os
from datetime import datetime

# Add the backend directory to sys.path so we can import models and database
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Eternalgy-MCP-RAG", "backend")
sys.path.append(backend_dir)

from sqlmodel import SQLModel, Session, select
from database import engine
from models import Workspace, BudgetTier, LeadStage, LeadTag

def apply_migration():
    print(f"[{datetime.utcnow()}] Starting M1 Foundation Migration...")
    
    # Create all tables (including new et_ prefixed ones)
    try:
        SQLModel.metadata.create_all(engine)
        print("Successfully created/verified all tables.")
    except Exception as e:
        print(f"Error creating tables: {e}")
        return

    # Seed default workspace if none exists
    with Session(engine) as session:
        statement = select(Workspace).where(Workspace.name == "Default Workspace")
        existing_ws = session.exec(statement).first()
        
        if not existing_ws:
            print("Seeding Default Workspace...")
            new_ws = Workspace(
                name="Default Workspace",
                timezone="UTC",
                budget_tier=BudgetTier.GREEN
            )
            session.add(new_ws)
            session.commit()
            print("Default Workspace seeded.")
        else:
            print("Default Workspace already exists.")

    print(f"[{datetime.utcnow()}] M1 Foundation Migration Completed.")

if __name__ == "__main__":
    apply_migration()
