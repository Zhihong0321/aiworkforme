import os
from sqlmodel import Session, SQLModel, create_engine
from src.infra.database import engine
from src.infra.seeding import (
    seed_identity_data, 
    seed_mcp_scripts, 
    seed_knowledge_retrieval_mcp,
    seed_catalog_mcp,
    seed_calendar_mcp,
    seed_default_assets
)
# Ensure models are loaded
from src.adapters.db import (
    user_models, agent_models, mcp_models, 
    chat_models, crm_models, tenant_models, 
    audit_models, links, calendar_models,
    catalog_models
)

print("Forcing database upgrade and seeding...")
SQLModel.metadata.create_all(engine)

default_tenant_id = seed_identity_data(engine)
seed_mcp_scripts()
seed_knowledge_retrieval_mcp(engine, default_tenant_id)
seed_catalog_mcp(engine, default_tenant_id)
seed_calendar_mcp(engine, default_tenant_id)
seed_default_assets(engine)

print("Seeding complete.")
