from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from routers import agents, mcp
from src.adapters.api.dependencies import AuthContext
from src.adapters.db.mcp_models import MCPServer
from src.adapters.db.tenant_models import Tenant
from src.adapters.db.user_models import User
from src.domain.entities.enums import Role


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Tenant(id=1, name="Tenant A"))
        db.add(Tenant(id=2, name="Tenant B"))
        db.commit()
        yield db


@pytest.fixture()
def auth_context() -> AuthContext:
    return AuthContext(
        user=User(id=10, email="tenant-user@test.local", password_hash="x", is_active=True),
        tenant=Tenant(id=1, name="Tenant A"),
        tenant_role=Role.TENANT_USER,
        is_platform_admin=False,
    )


def test_create_agent_accepts_frontend_payload(session: Session, auth_context: AuthContext):
    created = agents.create_agent(
        agents.AgentCreate(name="Prod Agent", system_prompt="You are helpful."),
        session=session,
        auth=auth_context,
    )
    assert created.id is not None
    assert created.name == "Prod Agent"
    assert created.system_prompt == "You are helpful."
    assert created.linked_mcp_ids == []
    assert created.linked_mcp_count == 0


def test_create_mcp_server_sets_tenant_from_auth_context(session: Session, auth_context: AuthContext):
    created = mcp.create_mcp_server(
        mcp.MCPServerCreate(
            name="Knowledge MCP",
            script="knowledge_retrieval.py",
            command="python",
            args="[]",
            cwd="/app",
            env_vars="{}",
        ),
        session=session,
        auth=auth_context,
    )
    assert created.id is not None
    assert int(created.tenant_id) == 1


def test_mcp_endpoints_are_tenant_scoped_for_list_and_delete(session: Session, auth_context: AuthContext):
    mock_manager = SimpleNamespace(
        get_mcp_status=_async_return({"status": "not found"}),
        terminate_mcp=_async_return(None),
        list_mcp_tools=_async_return([]),
        call_mcp_tool=_async_return({}),
    )

    own = mcp.create_mcp_server(
        mcp.MCPServerCreate(name="Own", script="own.py", args="[]", env_vars="{}"),
        session=session,
        auth=auth_context,
    )
    foreign = MCPServer(
        tenant_id=2,
        name="Foreign",
        script="foreign.py",
        command="python",
        args="[]",
        cwd="/app",
        env_vars="{}",
    )
    session.add(foreign)
    session.commit()
    session.refresh(foreign)

    listed = asyncio.run(
        mcp.list_mcp_servers(session=session, mcp_manager=mock_manager, auth=auth_context)
    )
    listed_ids = {int(row.id) for row in listed}
    assert int(own.id) in listed_ids
    assert int(foreign.id) not in listed_ids

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mcp.delete_mcp_server(
                server_id=int(foreign.id),
                session=session,
                mcp_manager=mock_manager,
                auth=auth_context,
            )
        )
    assert exc.value.status_code == 404


def _async_return(value):
    async def _inner(*_args, **_kwargs):
        return value

    return _inner
