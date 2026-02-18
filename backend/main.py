"""
MODULE: Main Application Entry Point
PURPOSE: FastAPI application setup, router inclusion, and startup/shutdown orchestration.
"""
import os
import logging
import asyncio
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from datetime import datetime

from src.infra.database import engine, get_session
from src.infra.migrations import apply_multitenant_additive_migration, apply_sql_migration_file
from src.infra.seeding import (
    seed_identity_data, 
    seed_mcp_scripts, 
    seed_knowledge_retrieval_mcp,
    seed_catalog_mcp,
    seed_calendar_mcp,
    seed_default_assets
)
from src.infra.security import hash_password # if needed, but likely seeding handles it
from src.adapters.api.dependencies import (
    mcp_manager,
    require_platform_admin,
    require_tenant_access,
)
from src.adapters.db.tenant_models import SystemSetting
from src.app.background_tasks import background_crm_loop
from src.app.background_tasks_messaging import background_outbound_dispatch_loop
from src.app.background_tasks_inbound import background_inbound_worker_loop

from routers import (
    analytics, auth, platform, mcp, chat, 
    agents, knowledge, settings, policy, 
    playground, workspaces, catalog, calendar, messaging
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Aiworkfor.me API",
    description="Backend API for the Aiworkfor.me AI Chatbot System.",
    version="0.1.0-refactored",
)

# Router Management
app.include_router(auth.router)
app.include_router(platform.router, dependencies=[Depends(require_platform_admin)])

tenant_dependencies = [Depends(require_tenant_access)]
app.include_router(mcp.router, dependencies=tenant_dependencies)
app.include_router(chat.router, dependencies=tenant_dependencies)
app.include_router(agents.router, dependencies=tenant_dependencies)
app.include_router(knowledge.router, dependencies=tenant_dependencies)
app.include_router(policy.router, dependencies=tenant_dependencies)
app.include_router(playground.router, dependencies=tenant_dependencies)
app.include_router(workspaces.router, dependencies=tenant_dependencies)
app.include_router(catalog.router, dependencies=tenant_dependencies)
app.include_router(analytics.router, dependencies=tenant_dependencies)
app.include_router(calendar.router, dependencies=tenant_dependencies)
app.include_router(messaging.router, dependencies=tenant_dependencies)
app.include_router(settings.router, dependencies=[Depends(require_platform_admin)])

# CORS Configuration
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from sqlmodel import Session, select, SQLModel
# Ensure all models are registered with SQLModel metadata
from src.adapters.db import (
    user_models, agent_models, mcp_models, 
    chat_models, crm_models, tenant_models, 
    audit_models, links, catalog_models,
    calendar_models, channel_models, messaging_models
)

@app.on_event("startup")
async def on_startup():
    logger.info("Initializing system...")
    try:
        # 0. Create Tables
        SQLModel.metadata.create_all(engine)
        
        # 1. Identity & Tables
        default_tenant_id = seed_identity_data(engine)
        
        # 2. Schema Migrations (Additive)
        apply_multitenant_additive_migration(engine, default_tenant_id)
        sql_migration_path = os.path.join(os.path.dirname(__file__), "sql", "messaging_m1_unified_schema.sql")
        apply_sql_migration_file(engine, sql_migration_path)
        
        # 3. Content Seeding
        seed_mcp_scripts()
        seed_knowledge_retrieval_mcp(engine, default_tenant_id)
        seed_catalog_mcp(engine, default_tenant_id)
        seed_calendar_mcp(engine, default_tenant_id)
        seed_default_assets(engine)
        
        # 4. Load System Settings
        with Session(engine) as session:
            # Load Z.ai key
            setting = session.get(SystemSetting, "zai_api_key")
            if setting and setting.value:
                logger.info("Loading Z.ai API Key from Database...")
                os.environ["ZAI_API_KEY"] = setting.value
            
            # Load UniAPI key
            setting = session.get(SystemSetting, "uniapi_key")
            if setting and setting.value:
                logger.info("Loading UniAPI Key from Database...")
                os.environ["UNIAPI_API_KEY"] = setting.value
            
            # Refresh LLM Router from DB
            from src.adapters.api.dependencies import refresh_llm_router_config
            refresh_llm_router_config(session)
                
    except Exception as e:
        logger.error(f"CRITICAL: Startup sequence failed: {e}")
        # Not exiting to allow health checks

    # 5. Background Loops
    asyncio.create_task(background_crm_loop())
    asyncio.create_task(background_outbound_dispatch_loop())
    asyncio.create_task(background_inbound_worker_loop())

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Shutting down...")
    await mcp_manager.shutdown_all_mcps()

# Health & Status
@app.get("/api/v1/", tags=["Status"])
def read_root():
    return {"status": "Z.ai Backend API is running (Refactored)"}

@app.get("/api/v1/health", tags=["Health Check"])
def health_check():
    return {"status": "ok", "service": "aiworkforme-backend", "version": "1.0.0-soc"}

@app.get("/api/v1/ready", tags=["Health Check"])
def readiness_check(db_session: Session = Depends(get_session)):
    from sqlalchemy import text
    try:
        db_session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Database unreachable")

# Frontend Static Hosting
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
