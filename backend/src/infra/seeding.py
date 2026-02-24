"""
MODULE: Data Seeding
PURPOSE: Ensures the system has default users, tenants, and assets on first run.
"""
import os
import shutil
import logging
from sqlmodel import Session, select
from sqlalchemy.engine import Engine

# Import models from adapters (since specific persistent models are needed)
from src.adapters.db.user_models import User, TenantMembership
from src.adapters.db.tenant_models import Tenant
from src.adapters.db.agent_models import Agent
from src.adapters.db.mcp_models import MCPServer
from src.domain.entities.enums import Role, TenantStatus
from src.adapters.db.crm_models import Workspace
from src.infra.security import hash_password

logger = logging.getLogger(__name__)

def seed_identity_data(engine: Engine) -> int:
    bootstrap_tenant_name = os.getenv("BOOTSTRAP_TENANT_NAME", "Default Tenant").strip()
    platform_admin_email = os.getenv("BOOTSTRAP_PLATFORM_ADMIN_EMAIL", "admin@aiworkfor.me").strip().lower()
    platform_admin_password = os.getenv("BOOTSTRAP_PLATFORM_ADMIN_PASSWORD", "admin12345")

    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.name == bootstrap_tenant_name)).first()
        if not tenant:
            tenant = Tenant(name=bootstrap_tenant_name)
            session.add(tenant)
            session.commit()
            session.refresh(tenant)
            logger.info(f"Seeded bootstrap tenant: {bootstrap_tenant_name}")

        admin = session.exec(select(User).where(User.email == platform_admin_email)).first()
        if not admin:
            admin = User(
                email=platform_admin_email,
                password_hash=hash_password(platform_admin_password),
                is_platform_admin=True,
            )
            session.add(admin)
            session.commit()
            session.refresh(admin)
            logger.info(f"Seeded platform admin: {platform_admin_email}")

            # Link admin to bootstrap tenant
            membership = TenantMembership(
                user_id=admin.id,
                tenant_id=tenant.id,
                role=Role.PLATFORM_ADMIN,
                is_active=True
            )
            session.add(membership)
            session.commit()
            logger.info(f"Linked admin to tenant {tenant.id}")

        return tenant.id

def seed_mcp_scripts():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    scripts_dir = os.getenv("MCP_SCRIPTS_DIR", os.path.join(base_dir, "mcp-runtime-scripts"))
    initial_dir = os.getenv("MCP_INITIAL_DIR", os.path.join(base_dir, "mcp_servers"))
    
    os.makedirs(scripts_dir, exist_ok=True)
    if os.path.exists(initial_dir):
        for item in os.listdir(initial_dir):
            src = os.path.join(initial_dir, item)
            dst = os.path.join(scripts_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            elif item.endswith((".py", ".json")):
                shutil.copy2(src, dst)
        logger.info("MCP scripts synced.")

def seed_default_assets(engine: Engine):
    # Get a tenant to attach to
    with Session(engine) as session:
        tenant = session.exec(select(Tenant).order_by(Tenant.id.asc())).first()
        if not tenant:
            return
        
        tenant_id = tenant.id
        
        # Ensure Default Agent exists
        agent = session.exec(select(Agent).where(Agent.tenant_id == tenant_id)).first()
        if not agent:
            agent = Agent(
                tenant_id=tenant_id,
                name="My AI Agent",
                system_prompt="You are a helpful assistant. Use your tools to find information and help the user.",
            )
            session.add(agent)
            session.commit()
            session.refresh(agent)
            logger.info("Seeded default agent.")

        # Ensure Default Workspace exists (Invisible 'Office')
        workspace = session.exec(select(Workspace).where(Workspace.tenant_id == tenant_id)).first()
        if not workspace:
            workspace = Workspace(
                tenant_id=tenant_id,
                name="Default Office",
                agent_id=agent.id,
                timezone="UTC"
            )
            session.add(workspace)
            session.commit()
            session.refresh(workspace)
            logger.info(f"Seeded default workspace: {workspace.id}")

            # Ensure Strategy exists for this workspace
            from src.adapters.db.crm_models import StrategyVersion, FollowUpPreset
            strategy = StrategyVersion(
                tenant_id=tenant_id,
                workspace_id=workspace.id,
                version_number=1,
                status="ACTIVE",
                tone="Professional and helpful.",
                objectives="Assist the user and answer questions.",
                objection_handling="Be polite and informative.",
                cta_rules="Offer further assistance.",
                followup_preset=FollowUpPreset.BALANCED
            )
            session.add(strategy)
            session.commit()
            logger.info("Seeded default strategy.")


            # Link default MCP servers
            mcp_scripts = ["knowledge_retrieval.py", "catalog_mcp.py", "calendar_mcp.py"]
            for script in mcp_scripts:
                mcp = session.exec(
                    select(MCPServer).where(
                        MCPServer.script == script,
                        MCPServer.tenant_id == tenant_id
                    )
                ).first()
                if mcp:
                    from src.adapters.db.links import AgentMCPServer
                    link = AgentMCPServer(agent_id=agent.id, mcp_server_id=mcp.id)
                    session.add(link)
            session.commit()
            logger.info("Linked default MCP servers to agent.")

def seed_knowledge_retrieval_mcp(engine: Engine, tenant_id: int):
    with Session(engine) as session:
        existing = session.exec(
            select(MCPServer).where(
                MCPServer.script == "knowledge_retrieval.py",
                MCPServer.tenant_id == tenant_id
            )
        ).first()
        
        if not existing:
            logger.info("Seeding Knowledge Retrieval MCP...")
            mcp = MCPServer(
                tenant_id=tenant_id,
                name="Knowledge Retrieval",
                script="knowledge_retrieval.py",
                command="python",
                args="[]",
                cwd="/app",
                env_vars="{}",
                status="stopped"
            )
            session.add(mcp)
            session.commit()

def seed_catalog_mcp(engine: Engine, tenant_id: int):
    with Session(engine) as session:
        existing = session.exec(
            select(MCPServer).where(
                MCPServer.script == "catalog_mcp.py",
                MCPServer.tenant_id == tenant_id
            )
        ).first()
        
        if not existing:
            logger.info("Seeding Catalog MCP...")
            mcp = MCPServer(
                tenant_id=tenant_id,
                name="Product Catalog",
                script="catalog_mcp.py",
                command="python",
                args="[]",
                cwd="/app",
                env_vars="{}",
                status="stopped"
            )
            session.add(mcp)
            session.commit()

def seed_calendar_mcp(engine: Engine, tenant_id: int):
    with Session(engine) as session:
        existing = session.exec(
            select(MCPServer).where(
                MCPServer.script == "calendar_mcp.py",
                MCPServer.tenant_id == tenant_id
            )
        ).first()
        
        if not existing:
            logger.info("Seeding Calendar Management MCP...")
            mcp = MCPServer(
                tenant_id=tenant_id,
                name="Calendar Management",
                script="calendar_mcp.py",
                command="python",
                args="[]",
                cwd="/app",
                env_vars="{}",
                status="stopped"
            )
            session.add(mcp)
            session.commit()
