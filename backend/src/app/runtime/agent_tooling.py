"""
Helpers for loading linked MCP tools and interpreting special outbound actions.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select

from src.adapters.api.dependencies import get_mcp_manager
from src.adapters.db.agent_models import Agent
from src.adapters.db.links import AgentMCPServer
from src.adapters.db.mcp_models import MCPServer


logger = logging.getLogger(__name__)

VOICE_NOTE_TOOL_NAME = "request_voice_note_followup"
VOICE_NOTE_SCRIPT = "voice_note_followup.py"
CALENDAR_TOOL_NAMES = {"book_appointment", "get_user_availability", "create_pending_appointment"}
CALENDAR_SCRIPT = "calendar_mcp.py"


def has_agent_mcp_script(session: Session, agent_id: int, script_name: str) -> bool:
    statement = (
        select(MCPServer)
        .join(AgentMCPServer, AgentMCPServer.mcp_server_id == MCPServer.id)
        .where(AgentMCPServer.agent_id == agent_id, MCPServer.script == script_name)
    )
    return session.exec(statement).first() is not None


def _runtime_paths() -> Tuple[str, str]:
    backend_dir = Path(__file__).resolve().parents[3]
    scripts_dir = os.getenv("MCP_SCRIPTS_DIR", str(backend_dir / "mcp-runtime-scripts"))
    fallback_cwd = str(backend_dir)
    return scripts_dir, fallback_cwd


def _resolved_server_launch(server: MCPServer) -> Tuple[List[str], str, Dict[str, str]]:
    scripts_dir, fallback_cwd = _runtime_paths()
    full_script_path = os.path.join(scripts_dir, server.script)

    env_vars: Dict[str, str] = {}
    if server.env_vars:
        try:
            loaded_env = json.loads(server.env_vars)
            if isinstance(loaded_env, dict):
                env_vars = {str(key): str(value) for key, value in loaded_env.items()}
        except Exception:
            env_vars = {}

    args: List[str] = []
    if server.args:
        try:
            loaded_args = json.loads(server.args)
            if isinstance(loaded_args, list):
                args = [str(item) for item in loaded_args]
        except Exception:
            args = []

    if not args and server.command == "python":
        args = [full_script_path]
    elif args and server.command == "python" and args[0] == server.script:
        args[0] = full_script_path

    cwd = str(server.cwd or "").strip() or fallback_cwd
    if not os.path.isdir(cwd):
        cwd = fallback_cwd

    return args, cwd, env_vars


async def load_agent_tools_for_runtime(
    session: Session,
    agent_id: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    manager = get_mcp_manager()
    agent = session.get(Agent, agent_id)
    linked_rows = session.exec(
        select(MCPServer)
        .join(AgentMCPServer, AgentMCPServer.mcp_server_id == MCPServer.id)
        .where(AgentMCPServer.agent_id == agent_id)
        .order_by(MCPServer.id.asc())
    ).all()

    tools: List[Dict[str, Any]] = []
    tool_meta: Dict[str, Dict[str, Any]] = {}

    for server in linked_rows:
        if str(server.script or "").strip() == CALENDAR_SCRIPT and not bool(getattr(agent, "calendar_enabled", False)):
            continue
        try:
            status = await manager.get_mcp_status(str(server.id))
            if status.get("status") == "not found":
                args, cwd, env_vars = _resolved_server_launch(server)
                await manager.spawn_mcp(
                    mcp_id=str(server.id),
                    command=server.command,
                    args=args,
                    cwd=cwd,
                    env=env_vars,
                )

            server_tools = await manager.list_mcp_tools(str(server.id))
            for tool in server_tools:
                tool_def = tool.model_dump(exclude_none=True)
                tool_name = str(tool_def["name"])
                parameters = dict(tool_def.get("inputSchema") or {"type": "object", "properties": {}})
                description = tool_def.get("description")
                if tool_name in CALENDAR_TOOL_NAMES:
                    properties = dict(parameters.get("properties") or {})
                    properties.pop("tenant_id", None)
                    properties.pop("agent_id", None)
                    parameters["properties"] = properties
                    required = [
                        item
                        for item in list(parameters.get("required") or [])
                        if item not in {"tenant_id", "agent_id"}
                    ]
                    if required:
                        parameters["required"] = required
                    else:
                        parameters.pop("required", None)
                    description = (
                        f"{description} Authenticated tenant and agent identity is injected automatically."
                        if description
                        else "Authenticated tenant and agent identity is injected automatically."
                    )
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": description,
                            "parameters": parameters,
                        },
                    }
                )
                tool_meta[tool_name] = {
                    "server_id": str(server.id),
                    "script": str(server.script),
                }
        except Exception as exc:
            logger.warning("Failed to prepare MCP tools for agent_id=%s server=%s: %s", agent_id, server.id, exc)

    return tools, tool_meta


def tool_result_to_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    if isinstance(result, list):
        chunks: List[str] = []
        for item in result:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(str(item.get("text") or ""))
                continue
            text_value = getattr(item, "text", None)
            item_type = getattr(item, "type", None)
            if item_type == "text" and text_value:
                chunks.append(str(text_value))
        if chunks:
            return "\n".join(chunk for chunk in chunks if chunk).strip()
    content = getattr(result, "content", None)
    if isinstance(content, list):
        chunks = []
        for item in content:
            item_type = getattr(item, "type", None)
            text_value = getattr(item, "text", None)
            if item_type == "text" and text_value:
                chunks.append(str(text_value))
        if chunks:
            return "\n".join(chunks).strip()
    return str(result)


def extract_voice_note_action(
    tool_name: str,
    tool_result_text: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if tool_name != VOICE_NOTE_TOOL_NAME:
        return None
    if meta and str(meta.get("script") or "") != VOICE_NOTE_SCRIPT:
        return None
    try:
        payload = json.loads(tool_result_text or "{}")
    except Exception:
        return None
    if not isinstance(payload, dict) or not bool(payload.get("approved")):
        return None

    spoken_text = str(payload.get("spoken_text") or "").strip()
    if not spoken_text:
        return None

    return {
        "message_type": "audio",
        "text_content": spoken_text,
        "tts_model": str(payload.get("tts_model") or "").strip() or "qwen3-tts-flash",
        "tts_voice": str(payload.get("tts_voice") or "").strip() or "kiki",
        "tts_instructions": str(payload.get("tts_instructions") or "").strip() or None,
        "trigger_reason": str(payload.get("trigger_reason") or "").strip() or None,
        "estimated_duration_seconds": payload.get("estimated_duration_seconds"),
        "cost_guard": str(payload.get("cost_guard") or "").strip() or None,
        "tool_name": tool_name,
    }
