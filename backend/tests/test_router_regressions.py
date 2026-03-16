from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool
from starlette.datastructures import Headers, UploadFile

from routers import agents, mcp
from src.adapters.api.dependencies import AuthContext
from src.adapters.db.channel_models import ChannelSession, ChannelType, SessionStatus
from src.adapters.db.crm_models import AICRMThreadState, AgentCRMProfile, Lead, Workspace
from src.adapters.db.messaging_models import UnifiedThread
from src.adapters.db.mcp_models import MCPServer
from src.adapters.db.tenant_models import Tenant
from src.adapters.db.user_models import User
from src.domain.entities.enums import Role
from src.app.runtime.sales_materials import validate_sales_material_upload


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


def test_create_agent_rejects_channel_already_claimed_by_another_agent(session: Session, auth_context: AuthContext):
    channel = ChannelSession(
        tenant_id=1,
        channel_type=ChannelType.WHATSAPP,
        session_identifier="wa-1",
        display_name="Primary WA",
        status=SessionStatus.ACTIVE,
        session_metadata={},
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)

    first = agents.create_agent(
        agents.AgentCreate(
            name="Agent One",
            system_prompt="Helpful",
            preferred_channel_session_id=int(channel.id),
        ),
        session=session,
        auth=auth_context,
    )
    assert first.preferred_channel_session_id == channel.id

    with pytest.raises(HTTPException) as exc:
        agents.create_agent(
            agents.AgentCreate(
                name="Agent Two",
                system_prompt="Helpful",
                preferred_channel_session_id=int(channel.id),
            ),
            session=session,
            auth=auth_context,
        )

    assert exc.value.status_code == 400
    assert "already assigned" in str(exc.value.detail)


def test_update_agent_rejects_channel_already_claimed_by_another_agent(session: Session, auth_context: AuthContext):
    channel_a = ChannelSession(
        tenant_id=1,
        channel_type=ChannelType.WHATSAPP,
        session_identifier="wa-a",
        display_name="WA A",
        status=SessionStatus.ACTIVE,
        session_metadata={},
    )
    channel_b = ChannelSession(
        tenant_id=1,
        channel_type=ChannelType.WHATSAPP,
        session_identifier="wa-b",
        display_name="WA B",
        status=SessionStatus.ACTIVE,
        session_metadata={},
    )
    session.add(channel_a)
    session.add(channel_b)
    session.commit()
    session.refresh(channel_a)
    session.refresh(channel_b)

    first = agents.create_agent(
        agents.AgentCreate(
            name="Agent One",
            system_prompt="Helpful",
            preferred_channel_session_id=int(channel_a.id),
        ),
        session=session,
        auth=auth_context,
    )
    second = agents.create_agent(
        agents.AgentCreate(
            name="Agent Two",
            system_prompt="Helpful",
            preferred_channel_session_id=int(channel_b.id),
        ),
        session=session,
        auth=auth_context,
    )

    with pytest.raises(HTTPException) as exc:
        agents.update_agent(
            agent_id=int(second.id),
            payload=agents.AgentUpdate(preferred_channel_session_id=int(channel_a.id)),
            session=session,
            auth=auth_context,
        )

    assert exc.value.status_code == 400
    assert "already assigned" in str(exc.value.detail)


def test_delete_agent_cleans_up_dependent_records(session: Session, auth_context: AuthContext):
    created_agent = agents.create_agent(
        agents.AgentCreate(name="Delete Me", system_prompt="Helpful"),
        session=session,
        auth=auth_context,
    )
    agent_id = int(created_agent.id)

    workspace = Workspace(tenant_id=1, name="Workspace A", agent_id=agent_id)
    session.add(workspace)
    session.commit()
    session.refresh(workspace)

    lead = Lead(
        tenant_id=1,
        workspace_id=workspace.id,
        external_id="+15550001111",
        name="Lead A",
        agent_id=agent_id,
    )
    session.add(lead)
    session.commit()
    session.refresh(lead)

    thread = UnifiedThread(
        tenant_id=1,
        lead_id=int(lead.id),
        agent_id=agent_id,
        channel="whatsapp",
    )
    session.add(thread)
    session.commit()
    session.refresh(thread)

    profile = AgentCRMProfile(
        tenant_id=1,
        agent_id=agent_id,
    )
    session.add(profile)

    state = AICRMThreadState(
        tenant_id=1,
        workspace_id=int(workspace.id),
        agent_id=agent_id,
        thread_id=int(thread.id),
        lead_id=int(lead.id),
    )
    session.add(state)

    server = mcp.create_mcp_server(
        mcp.MCPServerCreate(
            name="Cleanup MCP",
            script="cleanup.py",
            command="python",
            args="[]",
            cwd="/app",
            env_vars="{}",
        ),
        session=session,
        auth=auth_context,
    )
    agents.link_mcp_to_agent(
        agent_id=agent_id,
        server_id=int(server.id),
        session=session,
        auth=auth_context,
    )
    session.commit()

    deleted = agents.delete_agent(
        agent_id=agent_id,
        session=session,
        auth=auth_context,
    )

    session.refresh(workspace)
    session.refresh(lead)
    session.refresh(thread)

    assert deleted["message"] == "Agent deleted"
    assert session.get(agents.Agent, agent_id) is None
    assert workspace.agent_id is None
    assert lead.agent_id is None
    assert thread.agent_id is None
    assert session.exec(
        select(AgentCRMProfile).where(AgentCRMProfile.agent_id == agent_id)
    ).first() is None
    assert session.exec(
        select(AICRMThreadState).where(AICRMThreadState.agent_id == agent_id)
    ).first() is None
    assert session.exec(
        select(agents.AgentMCPServer).where(agents.AgentMCPServer.agent_id == agent_id)
    ).first() is None


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


def test_agent_mcp_link_and_unlink_are_tenant_scoped(session: Session, auth_context: AuthContext):
    created_agent = agents.create_agent(
        agents.AgentCreate(name="Linked Agent", system_prompt="Helpful"),
        session=session,
        auth=auth_context,
    )
    own_server = mcp.create_mcp_server(
        mcp.MCPServerCreate(
            name="Voice Note Follow-Up",
            script="voice_note_followup.py",
            command="python",
            args="[]",
            cwd="/app",
            env_vars="{}",
        ),
        session=session,
        auth=auth_context,
    )

    link_response = agents.link_mcp_to_agent(
        agent_id=int(created_agent.id),
        server_id=int(own_server.id),
        session=session,
        auth=auth_context,
    )
    assert "Linked" in link_response["message"]

    fetched = agents.get_agent(
        agent_id=int(created_agent.id),
        session=session,
        auth=auth_context,
    )
    assert int(own_server.id) in fetched.linked_mcp_ids

    unlink_response = agents.unlink_mcp_from_agent(
        agent_id=int(created_agent.id),
        server_id=int(own_server.id),
        session=session,
        auth=auth_context,
    )
    assert "Unlinked" in unlink_response["message"]

    fetched_after = agents.get_agent(
        agent_id=int(created_agent.id),
        session=session,
        auth=auth_context,
    )
    assert int(own_server.id) not in fetched_after.linked_mcp_ids


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


def test_agent_sales_material_upload_and_list_are_tenant_scoped(
    session: Session,
    auth_context: AuthContext,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr("src.app.runtime.sales_materials.SALES_MATERIALS_DIR", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)

    created = agents.create_agent(
        agents.AgentCreate(name="Sales Agent", system_prompt="Helpful"),
        session=session,
        auth=auth_context,
    )
    upload = UploadFile(
        file=BytesIO(b"%PDF-1.4 brochure body"),
        filename="brochure.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )
    request = SimpleNamespace(base_url="https://app.example.test/")

    material = asyncio.run(
        agents.upload_agent_sales_material(
            agent_id=int(created.id),
            request=request,
            file=upload,
            description="Use when customer asks for product brochure.",
            session=session,
            auth=auth_context,
        )
    )

    assert material.filename == "brochure.pdf"
    assert material.kind == "document"
    assert material.public_url == f"https://app.example.test/api/v1/public/sales-materials/{session.get(agents.AgentSalesMaterial, material.id).public_token}"

    listed = agents.list_agent_sales_materials(
        agent_id=int(created.id),
        session=session,
        auth=auth_context,
    )
    assert len(listed) == 1
    assert listed[0].description.startswith("Use when customer asks")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            agents.upload_agent_sales_material(
                agent_id=int(created.id),
                request=request,
                file=UploadFile(
                    file=BytesIO(b"not allowed"),
                    filename="notes.txt",
                    headers=Headers({"content-type": "text/plain"}),
                ),
                description="Invalid file",
                session=session,
                auth=auth_context,
            )
        )
    assert exc.value.status_code == 400


def test_agent_sales_material_links_accept_urls_and_youtube(
    session: Session,
    auth_context: AuthContext,
):
    created = agents.create_agent(
        agents.AgentCreate(name="Link Agent", system_prompt="Helpful"),
        session=session,
        auth=auth_context,
    )

    link_material = agents.create_agent_sales_material_link(
        agent_id=int(created.id),
        payload=agents.AgentSalesMaterialLinkCreate(
            url="https://example.com/pricing",
            description="Send this when someone wants the pricing page.",
        ),
        session=session,
        auth=auth_context,
    )
    youtube_material = agents.create_agent_sales_material_link(
        agent_id=int(created.id),
        payload=agents.AgentSalesMaterialLinkCreate(
            url="https://youtu.be/dQw4w9WgXcQ",
            description="Send this walkthrough video when someone asks how it works.",
        ),
        session=session,
        auth=auth_context,
    )

    assert link_material.source_type == "url"
    assert link_material.kind == "link"
    assert link_material.public_url == "https://example.com/pricing"
    assert youtube_material.kind == "youtube"
    assert youtube_material.public_url == "https://youtu.be/dQw4w9WgXcQ"

    listed = agents.list_agent_sales_materials(
        agent_id=int(created.id),
        session=session,
        auth=auth_context,
    )
    assert len(listed) == 2
    assert {item.kind for item in listed} == {"link", "youtube"}

    with pytest.raises(HTTPException) as exc:
        agents.create_agent_sales_material_link(
            agent_id=int(created.id),
            payload=agents.AgentSalesMaterialLinkCreate(
                url="ftp://example.com/file",
                description="Invalid URL",
            ),
            session=session,
            auth=auth_context,
        )
    assert exc.value.status_code == 400


def test_sales_material_upload_limit_accepts_up_to_30mb():
    accepted_pdf = validate_sales_material_upload(
        filename="brochure.pdf",
        content_type="application/pdf",
        content=b"%PDF" + (b"x" * ((30 * 1024 * 1024) - 4)),
    )
    accepted_image = validate_sales_material_upload(
        filename="banner.png",
        content_type="image/png",
        content=b"\x89PNG" + (b"x" * ((30 * 1024 * 1024) - 4)),
    )

    assert accepted_pdf["file_size_bytes"] == 30 * 1024 * 1024
    assert accepted_image["file_size_bytes"] == 30 * 1024 * 1024

    with pytest.raises(HTTPException) as exc:
        validate_sales_material_upload(
            filename="too-large.pdf",
            content_type="application/pdf",
            content=b"%PDF" + (b"x" * ((30 * 1024 * 1024) - 3)),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "PDF exceeds upload limit of 30MB"


def _async_return(value):
    async def _inner(*_args, **_kwargs):
        return value

    return _inner
