import os
from datetime import datetime
import shutil
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel, text, Session, select
from sqlalchemy.exc import OperationalError
import logging

from database import engine, get_session
from dependencies import mcp_manager, zai_client
from routers import mcp, chat, agents, knowledge, settings, policy, playground, workspaces
from runtime.agent_runtime import ConversationAgentRuntime
from runtime.crm_agent import CRMAgent
import asyncio
from models import SystemSetting, MCPServer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


app = FastAPI(
    title="Z.ai Chatbot System API",
    description="Backend API for the Z.ai Chatbot System.",
    version="0.1.0",
)

app.include_router(mcp.router)
app.include_router(chat.router)
app.include_router(agents.router)
app.include_router(knowledge.router)

app.include_router(settings.router)
app.include_router(policy.router)
app.include_router(playground.router)
app.include_router(workspaces.router)

# Set up CORS
origins = ["http://localhost:8080"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def seed_mcp_scripts():
    """Seeds initial MCP scripts to the persistent volume if missing."""
    # Determine paths relative to this file (main.py) to ensure compatibility 
    # with different environments (Docker, Railway/Nixpacks, Local).
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Default: ./mcp-runtime-scripts (relative to backend/)
    scripts_dir = os.getenv("MCP_SCRIPTS_DIR", os.path.join(base_dir, "mcp-runtime-scripts"))
    
    # Default: ./mcp_servers (relative to backend/)
    initial_dir = os.getenv("MCP_INITIAL_DIR", os.path.join(base_dir, "mcp_servers"))
    
    # Create target dir if it doesn't exist (it should be a volume, but just in case)
    os.makedirs(scripts_dir, exist_ok=True)
    
    if os.path.exists(initial_dir):
        logger.info(f"Syncing MCP scripts from {initial_dir} to {scripts_dir}...")
        for item_name in os.listdir(initial_dir):
            src_path = os.path.join(initial_dir, item_name)
            dst_path = os.path.join(scripts_dir, item_name)

            try:
                if os.path.isdir(src_path):
                    # dirs_exist_ok=True allows overwriting/merging
                    shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                    logger.info(f"Synced directory {item_name}")
                elif os.path.isfile(src_path) and (item_name.endswith(".py") or item_name.endswith(".json")):
                    shutil.copy2(src_path, dst_path)
                    logger.info(f"Synced file {item_name}")
            except Exception as e:
                logger.error(f"Failed to sync {item_name}: {e}")
    else:
        logger.warning(f"Initial MCP directory {initial_dir} not found. Skipping seeding.")

@app.on_event("startup")
async def on_startup():
    create_db_and_tables() # Enabled for automatic schema management
    
    # Run simple migration for new field
    try:
        pass
        # Auto-migration scripts removed per user request for manual DB management
    except Exception as e:
        logger.error(f"Migration script failed: {e}")

    seed_mcp_scripts()

    # Seed Knowledge Retrieval MCP if not exists
    try:
        with Session(engine) as session:
            statement = select(MCPServer).where(MCPServer.script == "knowledge_retrieval.py")
            existing_server = session.exec(statement).first()
            
            if not existing_server:
                logger.info("Seeding Knowledge Retrieval MCP...")
                new_server = MCPServer(
                    name="Knowledge Retrieval",
                    script="knowledge_retrieval.py",
                    command="python",
                    args="[]", 
                    cwd="/app",
                    env_vars="{}",
                    status="stopped"
                )
                session.add(new_server)
                session.commit()
    except Exception as e:
        logger.error(f"Failed to seed Knowledge Retrieval MCP: {e}")

    # Load Z.ai Key from DB if exists
    try:
        with Session(engine) as session:
            setting = session.get(SystemSetting, "zai_api_key")
            if setting and setting.value:
                logger.info("Loading Z.ai API Key from Database...")
                zai_client.update_api_key(setting.value)
    except Exception as e:
        logger.warning(f"Failed to load Z.ai key from DB on startup: {e}")

    # Start Real CRM Background Loop
    asyncio.create_task(background_crm_loop())
    
    # Seed default assets if empty
    seed_default_assets()

def seed_default_assets():
    """Ensure at least one agent and workspace exist for testing."""
    with Session(engine) as session:
        # Check for Agents
        from models import Agent, Workspace, BudgetTier
        if not session.exec(select(Agent)).first():
            logger.info("Seeding default Sales Agent...")
            agent = Agent(name="Default Sales Agent", system_prompt="You are a helpful sales assistant.", model="glm-4.7-flash")
            session.add(agent)
            session.commit()
            session.refresh(agent)
            
            # Create Workspace for this agent
            if not session.exec(select(Workspace)).first():
                logger.info("Seeding default Workspace...")
                ws = Workspace(name="Main Workspace", agent_id=agent.id, budget_tier=BudgetTier.GREEN)
                session.add(ws)
                session.commit()

async def background_crm_loop():
    """Real Automation Heartbeat: Runs Review and Dispatch loops."""
    logger.info("Starting REAL CRM Background Loop...")
    while True:
        try:
            with Session(engine) as session:
                runtime = ConversationAgentRuntime(session, zai_client)
                crm = CRMAgent(session, runtime)
                
                # 1. Review Loop: Plan follow-ups for new/neglected leads
                await crm.run_review_loop()
                
                # 2. Dispatcher: Execute turns for leads that are 'due'
                await crm.run_due_dispatcher()
                
        except Exception as e:
            logger.error(f"CRM Loop Error: {e}")
        
        # Interval for MVP: Check every 60 seconds
        await asyncio.sleep(60)

@app.on_event("shutdown")
async def on_shutdown():
    await mcp_manager.shutdown_all_mcps()


def check_database_connection():
    if not engine:
        return False, "DATABASE_URL not configured"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "Database connection successful"
    except OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        return False, "Database connection failed"
    except Exception as e:
        logger.error(f"An unexpected error occurred during database check: {e}")
        return False, "An unexpected error occurred"

@app.get("/api/v1/", tags=["Status"])
def read_root():
    """A simple endpoint to confirm the API is running."""
    return {"status": "Z.ai Backend API is running"}

@app.get("/api/v1/health", tags=["Health Check"])
def health_check():
    return {"status": "ok", "service": "eternalgy-backend", "version": "1.0.0-pilot"}

@app.get("/api/v1/ready", tags=["Health Check"])
def readiness_check(db_session: Session = Depends(get_session)):
    from sqlalchemy import text
    try:
        # Check DB connectivity
        db_session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Database unreachable")

# ---------- Frontend Static Hosting ----------
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend-dist")
INDEX_PATH = os.path.join(FRONTEND_DIR, "index.html")

if os.path.isdir(FRONTEND_DIR):
    assets_dir = os.path.join(FRONTEND_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")


@app.get("/", include_in_schema=False)
def serve_frontend_index():
    if os.path.isfile(INDEX_PATH):
        return FileResponse(INDEX_PATH)
    return {"status": "Z.ai Backend API is running (frontend not built)"}


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend_spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    if os.path.isfile(INDEX_PATH):
        return FileResponse(INDEX_PATH)
    raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
