from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from routers import chat
from src.adapters.api.dependencies import AuthContext
from src.adapters.db.agent_models import Agent
from src.adapters.db.chat_models import ChatRequest
from src.adapters.db.links import AgentMCPServer
from src.adapters.db.mcp_models import MCPServer
from src.adapters.db.tenant_models import Tenant
from src.adapters.db.user_models import User
from src.domain.entities.enums import Role


class _FakeTool:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, exclude_none=True):
        return dict(self._payload)


class _FakeMCPManager:
    def __init__(self):
        self.spawn_calls = []
        self.tool_calls = []

    async def get_mcp_status(self, _mcp_id):
        return {"status": "not found"}

    async def spawn_mcp(self, *args, **kwargs):
        self.spawn_calls.append((args, kwargs))
        return {"status": "registered"}

    async def list_mcp_tools(self, _mcp_id):
        return [
            _FakeTool(
                {
                    "name": "book_appointment",
                    "description": "Book an appointment in the calendar.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "tenant_id": {"type": "integer"},
                            "agent_id": {"type": "integer"},
                            "title": {"type": "string"},
                            "start_time": {"type": "string"},
                            "end_time": {"type": "string"},
                        },
                        "required": ["tenant_id", "agent_id", "title", "start_time", "end_time"],
                    },
                }
            )
        ]

    async def call_mcp_tool(self, server_id, tool_name, tool_args):
        self.tool_calls.append((server_id, tool_name, dict(tool_args)))
        return "Successfully booked appointment: Demo"


class _FakeLLMRouter:
    def __init__(self):
        self.calls = []
        self._responses = [
            SimpleNamespace(
                content=None,
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "book_appointment",
                            "arguments": json.dumps(
                                {
                                    "tenant_id": 999,
                                    "agent_id": 999,
                                    "title": "Demo call",
                                    "start_time": "2026-03-20T10:00:00",
                                    "end_time": "2026-03-20T10:30:00",
                                }
                            ),
                        },
                    }
                ],
            ),
            SimpleNamespace(
                content="Booked for March 20 at 10:00.",
                tool_calls=None,
            ),
        ]

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def _make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_chat_route_injects_calendar_identity_and_requires_tool_use_for_scheduling():
    session = _make_session()
    tenant = Tenant(id=1, name="Tenant A")
    user = User(id=10, email="user@test.local", password_hash="x", is_active=True)
    agent = Agent(id=100, tenant_id=1, name="Sales Agent", system_prompt="Helpful.", calendar_enabled=True)
    mcp_server = MCPServer(
        id=77,
        tenant_id=1,
        name="Calendar Management",
        script="calendar_mcp.py",
        command="python",
        args="[]",
        cwd="/app",
        env_vars="{}",
    )
    link = AgentMCPServer(agent_id=100, mcp_server_id=77)
    session.add(tenant)
    session.add(user)
    session.add(agent)
    session.add(mcp_server)
    session.add(link)
    session.commit()

    auth = AuthContext(
        user=user,
        tenant=tenant,
        tenant_role=Role.TENANT_USER,
        is_platform_admin=False,
    )
    mcp_manager = _FakeMCPManager()
    llm_router = _FakeLLMRouter()

    response = asyncio.run(
        chat.chat_with_agent(
            ChatRequest(agent_id=100, message="Please book an appointment for tomorrow at 10am."),
            session=session,
            mcp_manager=mcp_manager,
            llm_router=llm_router,
            auth=auth,
        )
    )

    assert response.response == "Booked for March 20 at 10:00."
    assert llm_router.calls[0]["tool_choice"] == "required"
    tool_schema = llm_router.calls[0]["tools"][0]["function"]["parameters"]
    assert "tenant_id" not in tool_schema["properties"]
    assert "agent_id" not in tool_schema["properties"]
    assert "tenant_id" not in tool_schema.get("required", [])
    assert "agent_id" not in tool_schema.get("required", [])
    assert mcp_manager.tool_calls == [
        (
            "77",
            "book_appointment",
            {
                "tenant_id": 1,
                "agent_id": 100,
                "title": "Demo call",
                "start_time": "2026-03-20T10:00:00",
                "end_time": "2026-03-20T10:30:00",
            },
        )
    ]
