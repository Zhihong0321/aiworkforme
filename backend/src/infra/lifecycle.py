"""
MODULE: Application Lifecycle
PURPOSE: Startup/shutdown orchestration for schema, seeding, and background loops.
DOES: Run startup sequence and expose startup health snapshot.
DOES NOT: Define HTTP routes or router registration.
INVARIANTS: Startup order remains additive and non-destructive.
SAFE CHANGE: Extend startup steps after schema compatibility checks.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict

from sqlmodel import SQLModel, Session

from src.adapters.api.dependencies import (
    mcp_manager,
    refresh_llm_router_config,
    refresh_llm_task_model_config,
    refresh_provider_keys_from_db,
)
from src.adapters.db import (  # noqa: F401
    agent_models,
    audit_models,
    calendar_models,
    catalog_models,
    channel_models,
    chat_models,
    crm_models,
    links,
    mcp_models,
    messaging_models,
    tenant_models,
    user_models,
)
from src.app.background_tasks import background_crm_loop
from src.app.background_tasks_ai_crm import background_ai_crm_loop
from src.app.background_tasks_inbound import background_inbound_worker_loop
from src.app.background_tasks_messaging import background_outbound_dispatch_loop
from src.infra.database import engine
from src.infra.migrations import (
    apply_ai_crm_additive_migration,
    apply_legacy_table_rename_migration,
    apply_message_usage_columns_migration,
    apply_multitenant_additive_migration,
    apply_sql_migration_file,
)
from src.infra.schema_checks import evaluate_message_schema_compat
from src.infra.seeding import (
    seed_calendar_mcp,
    seed_catalog_mcp,
    seed_default_assets,
    seed_identity_data,
    seed_knowledge_retrieval_mcp,
    seed_mcp_scripts,
)

logger = logging.getLogger(__name__)

STARTUP_HEALTH: Dict[str, Any] = {
    "ready": False,
    "schema": {},
    "checked_at": None,
}


async def run_startup_sequence() -> None:
    """Initialize schema, seed baseline data, then start background loops."""
    logger.info("Initializing system...")
    try:
        apply_legacy_table_rename_migration(engine)
        SQLModel.metadata.create_all(engine)

        default_tenant_id = seed_identity_data(engine)
        apply_multitenant_additive_migration(engine, default_tenant_id)
        apply_message_usage_columns_migration(engine)

        sql_migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "sql",
            "messaging_m1_unified_schema.sql",
        )
        try:
            apply_sql_migration_file(engine, sql_migration_path)
        except Exception:
            logger.exception("Messaging SQL migration failed; continuing with additive fallback migration.")

        apply_message_usage_columns_migration(engine)
        apply_ai_crm_additive_migration(engine)

        schema_check = evaluate_message_schema_compat(engine)
        STARTUP_HEALTH["schema"] = schema_check
        STARTUP_HEALTH["ready"] = bool(schema_check.get("ok"))
        STARTUP_HEALTH["checked_at"] = datetime.utcnow().isoformat()
        if not STARTUP_HEALTH["ready"]:
            logger.error(
                "Schema compatibility failed at startup. Missing columns: %s",
                schema_check.get("missing_columns"),
            )

        seed_mcp_scripts()
        seed_knowledge_retrieval_mcp(engine, default_tenant_id)
        seed_catalog_mcp(engine, default_tenant_id)
        seed_calendar_mcp(engine, default_tenant_id)
        seed_default_assets(engine)

        with Session(engine) as session:
            refresh_provider_keys_from_db(session)
            refresh_llm_router_config(session)
            refresh_llm_task_model_config(session)
            logger.info("Provider keys + LLM routing config loaded from DB.")
    except Exception as exc:
        logger.error("CRITICAL: Startup sequence failed: %s", exc)
        STARTUP_HEALTH["ready"] = False
        STARTUP_HEALTH["checked_at"] = datetime.utcnow().isoformat()

    asyncio.create_task(background_crm_loop())
    asyncio.create_task(background_outbound_dispatch_loop())
    asyncio.create_task(background_inbound_worker_loop())
    asyncio.create_task(background_ai_crm_loop())


async def run_shutdown_sequence() -> None:
    """Stop process-managed MCP services during API shutdown."""
    logger.info("Shutting down...")
    await mcp_manager.shutdown_all_mcps()
