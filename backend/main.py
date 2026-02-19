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
from src.infra.migrations import (
    apply_multitenant_additive_migration,
    apply_sql_migration_file,
    apply_message_usage_columns_migration,
)
from src.infra.schema_checks import evaluate_message_schema_compat
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
    playground, workspaces, catalog, calendar, messaging, debug
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
STARTUP_HEALTH = {
    "ready": False,
    "schema": {},
    "checked_at": None,
}

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
app.include_router(debug.router)

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
        # Ensure et_messages has LLM usage columns before any SQL script/indexes rely on them.
        apply_message_usage_columns_migration(engine)
        sql_migration_path = os.path.join(os.path.dirname(__file__), "sql", "messaging_m1_unified_schema.sql")
        try:
            apply_sql_migration_file(engine, sql_migration_path)
        except Exception:
            logger.exception("Messaging SQL migration failed; continuing with additive fallback migration.")
        # Re-run to guarantee columns exist even if the SQL migration partially failed.
        apply_message_usage_columns_migration(engine)

        schema_check = evaluate_message_schema_compat(engine)
        STARTUP_HEALTH["schema"] = schema_check
        STARTUP_HEALTH["ready"] = bool(schema_check.get("ok"))
        STARTUP_HEALTH["checked_at"] = datetime.utcnow().isoformat()
        if not STARTUP_HEALTH["ready"]:
            logger.error(
                "Schema compatibility failed at startup. Missing columns: %s",
                schema_check.get("missing_columns"),
            )
        
        # 3. Content Seeding
        seed_mcp_scripts()
        seed_knowledge_retrieval_mcp(engine, default_tenant_id)
        seed_catalog_mcp(engine, default_tenant_id)
        seed_calendar_mcp(engine, default_tenant_id)
        seed_default_assets(engine)
        
        # 4. Load System Settings
        with Session(engine) as session:
            # Load Z.ai key
            zai_setting = session.get(SystemSetting, "zai_api_key")
            if zai_setting and zai_setting.value:
                logger.info("Loading Z.ai API Key from Database...")
                os.environ["ZAI_API_KEY"] = zai_setting.value
            
            # Load UniAPI key
            uni_setting = session.get(SystemSetting, "uniapi_key")
            if uni_setting and uni_setting.value:
                logger.info("Loading UniAPI Key from Database...")
                os.environ["UNIAPI_API_KEY"] = uni_setting.value

            # Re-initialise provider instances with the loaded keys.
            # ZaiProvider / UniAPIProvider are created at import time (before startup),
            # so they must be explicitly re-inited after the keys are in os.environ.
            from src.adapters.api.dependencies import llm_router
            zai_provider = llm_router.providers.get("zai")
            if zai_provider and zai_setting and zai_setting.value:
                zai_provider.api_key = zai_setting.value
                zai_provider._init_client()
                logger.info("ZaiProvider re-initialised with DB key.")

            uniapi_provider = llm_router.providers.get("uniapi")
            if uniapi_provider and uni_setting and uni_setting.value:
                uniapi_provider.api_key = uni_setting.value
                uniapi_provider._init_client()
                logger.info("UniAPIProvider re-initialised with DB key.")

            # Refresh LLM Router routing config from DB
            from src.adapters.api.dependencies import refresh_llm_router_config
            refresh_llm_router_config(session)
                
    except Exception as e:
        logger.error(f"CRITICAL: Startup sequence failed: {e}")
        STARTUP_HEALTH["ready"] = False
        STARTUP_HEALTH["checked_at"] = datetime.utcnow().isoformat()
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
    from fastapi import HTTPException as FastAPIHTTPException
    try:
        db_session.execute(text("SELECT 1"))
        live_schema = evaluate_message_schema_compat(engine)
        startup_ready = bool(STARTUP_HEALTH.get("ready"))
        schema_ready = bool(live_schema.get("ok"))
        if not startup_ready or not schema_ready:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "not_ready",
                    "reason": "schema_incompatible",
                    "startup_health": STARTUP_HEALTH,
                    "live_schema": live_schema,
                },
            )
        return {
            "status": "ready",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "schema": {"ok": True},
        }
    except FastAPIHTTPException:
        raise
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
