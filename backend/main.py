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
from dependencies import (
    mcp_manager,
    require_platform_admin,
    require_tenant_access,
    zai_client,
)
from routers import analytics, auth, platform, mcp, chat, agents, knowledge, settings, policy, playground, workspaces
from runtime.agent_runtime import ConversationAgentRuntime
from runtime.crm_agent import CRMAgent
import asyncio
from tenacity import retry, stop_after_attempt, wait_fixed
from models import MCPServer, Role, SystemSetting, Tenant, TenantMembership, TenantStatus, User
from security import hash_password

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


app = FastAPI(
    title="Aiworkfor.me API",
    description="Backend API for the Aiworkfor.me AI Chatbot System.",
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(platform.router, dependencies=[Depends(require_platform_admin)])

tenant_dependencies = [Depends(require_tenant_access)]
app.include_router(mcp.router, dependencies=tenant_dependencies)
app.include_router(chat.router, dependencies=tenant_dependencies)
app.include_router(agents.router, dependencies=tenant_dependencies)
app.include_router(knowledge.router, dependencies=tenant_dependencies)
app.include_router(policy.router, dependencies=tenant_dependencies)
app.include_router(policy.legacy_router, dependencies=tenant_dependencies)
app.include_router(playground.router, dependencies=tenant_dependencies)
app.include_router(workspaces.router, dependencies=tenant_dependencies)
app.include_router(analytics.router, dependencies=tenant_dependencies)
app.include_router(settings.router, dependencies=[Depends(require_platform_admin)])

# Set up CORS - allow all for pilot/local development to avoid blocking user
origins = ["*"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
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


def apply_multitenant_additive_migration(default_tenant_id: int):
    """
    Add tenant_id columns/indexes to legacy tenant-owned tables and backfill existing rows.
    This is an additive migration to support in-place refactors on existing environments.
    """
    if engine.dialect.name != "postgresql":
        logger.warning(
            "Skipping additive tenant migration for non-PostgreSQL dialect: %s",
            engine.dialect.name,
        )
        return

    tenant_owned_tables = [
        "zairag_agents",
        "zairag_mcp_servers",
        "zairag_agent_knowledge_files",
        "zairag_chat_sessions",
        "zairag_chat_messages",
        "et_workspaces",
        "et_strategy_versions",
        "et_leads",
        "et_conversation_threads",
        "et_chat_messages",
        "et_policy_decisions",
        "et_outreach_attestations",
        "et_lead_memories",
    ]

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE zairag_agents ADD COLUMN IF NOT EXISTS tenant_id INTEGER"))
        conn.execute(text("ALTER TABLE zairag_mcp_servers ADD COLUMN IF NOT EXISTS tenant_id INTEGER"))
        conn.execute(text("ALTER TABLE zairag_agent_knowledge_files ADD COLUMN IF NOT EXISTS tenant_id INTEGER"))
        conn.execute(text("ALTER TABLE zairag_chat_sessions ADD COLUMN IF NOT EXISTS tenant_id INTEGER"))
        conn.execute(text("ALTER TABLE zairag_chat_messages ADD COLUMN IF NOT EXISTS tenant_id INTEGER"))

        conn.execute(text("ALTER TABLE et_workspaces ADD COLUMN IF NOT EXISTS tenant_id INTEGER"))
        conn.execute(text("ALTER TABLE et_strategy_versions ADD COLUMN IF NOT EXISTS tenant_id INTEGER"))
        conn.execute(text("ALTER TABLE et_leads ADD COLUMN IF NOT EXISTS tenant_id INTEGER"))
        conn.execute(text("ALTER TABLE et_conversation_threads ADD COLUMN IF NOT EXISTS tenant_id INTEGER"))
        conn.execute(text("ALTER TABLE et_chat_messages ADD COLUMN IF NOT EXISTS tenant_id INTEGER"))
        conn.execute(text("ALTER TABLE et_policy_decisions ADD COLUMN IF NOT EXISTS tenant_id INTEGER"))
        conn.execute(text("ALTER TABLE et_outreach_attestations ADD COLUMN IF NOT EXISTS tenant_id INTEGER"))
        conn.execute(text("ALTER TABLE et_lead_memories ADD COLUMN IF NOT EXISTS tenant_id INTEGER"))

        conn.execute(
            text("UPDATE et_workspaces SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": default_tenant_id},
        )
        conn.execute(
            text("UPDATE zairag_agents SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": default_tenant_id},
        )
        conn.execute(
            text("UPDATE zairag_mcp_servers SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": default_tenant_id},
        )
        conn.execute(
            text(
                """
                UPDATE zairag_agent_knowledge_files f
                SET tenant_id = a.tenant_id
                FROM zairag_agents a
                WHERE f.agent_id = a.id AND f.tenant_id IS NULL
                """
            )
        )
        conn.execute(
            text("UPDATE zairag_agent_knowledge_files SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": default_tenant_id},
        )
        conn.execute(
            text(
                """
                UPDATE zairag_chat_sessions s
                SET tenant_id = a.tenant_id
                FROM zairag_agents a
                WHERE s.agent_id = a.id AND s.tenant_id IS NULL
                """
            )
        )
        conn.execute(
            text("UPDATE zairag_chat_sessions SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": default_tenant_id},
        )
        conn.execute(
            text(
                """
                UPDATE zairag_chat_messages m
                SET tenant_id = s.tenant_id
                FROM zairag_chat_sessions s
                WHERE m.chat_session_id = s.id AND m.tenant_id IS NULL
                """
            )
        )
        conn.execute(
            text("UPDATE zairag_chat_messages SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": default_tenant_id},
        )
        conn.execute(
            text(
                """
                UPDATE et_strategy_versions sv
                SET tenant_id = w.tenant_id
                FROM et_workspaces w
                WHERE sv.workspace_id = w.id AND sv.tenant_id IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE et_leads l
                SET tenant_id = w.tenant_id
                FROM et_workspaces w
                WHERE l.workspace_id = w.id AND l.tenant_id IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE et_conversation_threads t
                SET tenant_id = w.tenant_id
                FROM et_workspaces w
                WHERE t.workspace_id = w.id AND t.tenant_id IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE et_chat_messages cm
                SET tenant_id = t.tenant_id
                FROM et_conversation_threads t
                WHERE cm.thread_id = t.id AND cm.tenant_id IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE et_policy_decisions pd
                SET tenant_id = w.tenant_id
                FROM et_workspaces w
                WHERE pd.workspace_id = w.id AND pd.tenant_id IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE et_outreach_attestations oa
                SET tenant_id = w.tenant_id
                FROM et_workspaces w
                WHERE oa.workspace_id = w.id AND oa.tenant_id IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE et_lead_memories lm
                SET tenant_id = l.tenant_id
                FROM et_leads l
                WHERE lm.lead_id = l.id AND lm.tenant_id IS NULL
                """
            )
        )
        conn.execute(
            text("UPDATE et_strategy_versions SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": default_tenant_id},
        )
        conn.execute(
            text("UPDATE et_leads SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": default_tenant_id},
        )
        conn.execute(
            text("UPDATE et_conversation_threads SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": default_tenant_id},
        )
        conn.execute(
            text("UPDATE et_chat_messages SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": default_tenant_id},
        )
        conn.execute(
            text("UPDATE et_policy_decisions SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": default_tenant_id},
        )
        conn.execute(
            text("UPDATE et_outreach_attestations SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": default_tenant_id},
        )
        conn.execute(
            text("UPDATE et_lead_memories SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": default_tenant_id},
        )

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_zairag_agents_tenant_id ON zairag_agents (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_zairag_mcp_servers_tenant_id ON zairag_mcp_servers (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_zairag_agent_knowledge_files_tenant_id ON zairag_agent_knowledge_files (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_zairag_chat_sessions_tenant_id ON zairag_chat_sessions (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_zairag_chat_messages_tenant_id ON zairag_chat_messages (tenant_id)"))

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_et_workspaces_tenant_id ON et_workspaces (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_et_strategy_versions_tenant_id ON et_strategy_versions (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_et_leads_tenant_id ON et_leads (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_et_conversation_threads_tenant_id ON et_conversation_threads (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_et_chat_messages_tenant_id ON et_chat_messages (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_et_policy_decisions_tenant_id ON et_policy_decisions (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_et_outreach_attestations_tenant_id ON et_outreach_attestations (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_et_lead_memories_tenant_id ON et_lead_memories (tenant_id)"))

        # M2 hardening gate: tenant_id must be enforced at schema level.
        for table_name in tenant_owned_tables:
            constraint_name = f"{table_name}_tenant_id_fkey"
            conn.execute(
                text(
                    f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1
                            FROM pg_constraint
                            WHERE conname = '{constraint_name}'
                              AND conrelid = '{table_name}'::regclass
                        ) THEN
                            ALTER TABLE {table_name}
                            ADD CONSTRAINT {constraint_name}
                            FOREIGN KEY (tenant_id) REFERENCES et_tenants(id);
                        END IF;
                    END
                    $$;
                    """
                )
            )
            conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN tenant_id SET NOT NULL"))

            null_count = conn.execute(
                text(f"SELECT COUNT(*) FROM {table_name} WHERE tenant_id IS NULL")
            ).scalar_one()
            if null_count:
                raise RuntimeError(
                    f"Migration failed: {table_name}.tenant_id still has {null_count} NULL rows"
                )


def seed_identity_data() -> int:
    bootstrap_tenant_name = os.getenv("BOOTSTRAP_TENANT_NAME", "Default Tenant").strip() or "Default Tenant"
    platform_admin_email = os.getenv("BOOTSTRAP_PLATFORM_ADMIN_EMAIL", "admin@aiworkfor.me").strip().lower()
    platform_admin_password = os.getenv("BOOTSTRAP_PLATFORM_ADMIN_PASSWORD", "admin12345")
    tenant_admin_email = os.getenv("BOOTSTRAP_TENANT_ADMIN_EMAIL", "tenant-admin@aiworkfor.me").strip().lower()
    tenant_admin_password = os.getenv("BOOTSTRAP_TENANT_ADMIN_PASSWORD", "tenant12345")

    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.name == bootstrap_tenant_name)).first()
        if not tenant:
            tenant = Tenant(name=bootstrap_tenant_name)
            session.add(tenant)
            session.commit()
            session.refresh(tenant)
            logger.info("Seeded bootstrap tenant: %s", bootstrap_tenant_name)

        platform_admin = session.exec(select(User).where(User.email == platform_admin_email)).first()
        if not platform_admin:
            platform_admin = User(
                email=platform_admin_email,
                password_hash=hash_password(platform_admin_password),
                is_platform_admin=True,
            )
            session.add(platform_admin)
            session.commit()
            logger.info("Seeded bootstrap platform admin user: %s", platform_admin_email)
        elif not platform_admin.is_platform_admin:
            platform_admin.is_platform_admin = True
            session.add(platform_admin)
            session.commit()
            logger.info("Updated bootstrap platform admin role for: %s", platform_admin_email)

        tenant_admin = session.exec(select(User).where(User.email == tenant_admin_email)).first()
        if not tenant_admin:
            tenant_admin = User(
                email=tenant_admin_email,
                password_hash=hash_password(tenant_admin_password),
                is_platform_admin=False,
            )
            session.add(tenant_admin)
            session.commit()
            session.refresh(tenant_admin)
            logger.info("Seeded bootstrap tenant admin user: %s", tenant_admin_email)

        membership = session.exec(
            select(TenantMembership).where(
                TenantMembership.user_id == tenant_admin.id,
                TenantMembership.tenant_id == tenant.id,
            )
        ).first()
        if not membership:
            membership = TenantMembership(
                user_id=tenant_admin.id,
                tenant_id=tenant.id,
                role=Role.TENANT_ADMIN,
                is_active=True,
            )
            session.add(membership)
            session.commit()
            logger.info("Seeded tenant admin membership for tenant_id=%s", tenant.id)

        return tenant.id

@retry(stop=stop_after_attempt(5), wait=wait_fixed(5))
def perform_db_startup():
    """Resiliently initialize database tables and seed data."""
    logger.info("Initializing database...")
    create_db_and_tables()
    default_tenant_id = seed_identity_data()
    apply_multitenant_additive_migration(default_tenant_id)
    
    seed_mcp_scripts()

    # Seed Knowledge Retrieval MCP if not exists
    try:
        with Session(engine) as session:
            statement = select(MCPServer).where(
                MCPServer.script == "knowledge_retrieval.py",
                MCPServer.tenant_id == default_tenant_id,
            )
            existing_server = session.exec(statement).first()
            
            if not existing_server:
                logger.info("Seeding Knowledge Retrieval MCP...")
                new_server = MCPServer(
                    tenant_id=default_tenant_id,
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
        raise # Let tenacity retry

    # Load Z.ai Key from DB if exists
    try:
        with Session(engine) as session:
            setting = session.get(SystemSetting, "zai_api_key")
            if setting and setting.value:
                logger.info("Loading Z.ai API Key from Database...")
                zai_client.update_api_key(setting.value)
    except Exception as e:
        logger.warning(f"Failed to load Z.ai key from DB on startup: {e}")
        # Not fatal, but log it

    # Seed default assets if empty
    seed_default_assets()

@app.on_event("startup")
async def on_startup():
    try:
        perform_db_startup()
    except Exception as e:
        logger.error(f"CRITICAL: System could not connect to database after retries: {e}")
        # We don't exit(1) here to allow the process to stay alive and show health errors 
        # instead of an infinite restart loop on some platforms.

    # Start Real CRM Background Loop
    asyncio.create_task(background_crm_loop())

def seed_default_assets():
    """Ensure at least one agent and workspace exist for testing."""
    with Session(engine) as session:
        default_tenant = session.exec(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE).order_by(Tenant.id.asc())
        ).first()
        if not default_tenant:
            logger.warning("No active tenant found; skipping default assets seeding.")
            return

        # Check for Agents
        from models import Agent, Workspace, BudgetTier
        if not session.exec(select(Agent).where(Agent.tenant_id == default_tenant.id)).first():
            logger.info("Seeding default Sales Agent...")
            agent = Agent(
                tenant_id=default_tenant.id,
                name="Default Sales Agent",
                system_prompt="You are a helpful sales assistant.",
                model="glm-4.7-flash",
            )
            session.add(agent)
            session.commit()
            session.refresh(agent)
            
            # Create Workspace for this agent
            if not session.exec(select(Workspace).where(Workspace.tenant_id == default_tenant.id)).first():
                logger.info("Seeding default Workspace...")
                ws = Workspace(
                    tenant_id=default_tenant.id,
                    name="Main Workspace",
                    agent_id=agent.id,
                    budget_tier=BudgetTier.GREEN,
                )
                session.add(ws)
                session.commit()
        elif not session.exec(select(Workspace).where(Workspace.tenant_id == default_tenant.id)).first():
            default_agent = session.exec(
                select(Agent)
                .where(Agent.tenant_id == default_tenant.id)
                .order_by(Agent.id.asc())
            ).first()
            logger.info("Seeding default Workspace for existing tenant agent...")
            ws = Workspace(
                tenant_id=default_tenant.id,
                name="Main Workspace",
                agent_id=default_agent.id if default_agent else None,
                budget_tier=BudgetTier.GREEN,
            )
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
    return {"status": "ok", "service": "aiworkforme-backend", "version": "1.0.0-pilot"}

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
