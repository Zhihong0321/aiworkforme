"""
MODULE: MCP Adapter Manager
PURPOSE: Handles the spawning, tool listing, and execution of Model Context Protocol (MCP) servers.
INVARIANTS: Maintains stateless configuration but stateful process tracking in-memory.
HOW TO MODIFY: Update list_mcp_tools/call_mcp_tool to change how communication with stdio processes is handled.
"""
import asyncio
import os
import logging
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import time

from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession
from mcp.types import Tool 
from mcp import StdioServerParameters 

logger = logging.getLogger(__name__)

class MCPManager:
    def __init__(self):
        self.server_configs: Dict[str, StdioServerParameters] = {}
        self.server_states: Dict[str, Dict[str, Any]] = {} # mcp_id -> {status, last_heartbeat, last_error, ...}
        self.default_timeout = 30 # seconds
        self.tools_cache_ttl_s = int(os.getenv("MCP_TOOLS_CACHE_TTL_S", "300"))
        self._tools_cache: Dict[str, Dict[str, Any]] = {}  # mcp_id -> {at: float, tools: list[Tool]}
        self._tools_locks: Dict[str, asyncio.Lock] = {}

    async def spawn_mcp(self, mcp_id: str, command: str, args: list[str], cwd: str = "/app", env: dict = None) -> dict:
        """Registers an MCP server configuration."""
        logger.info(f"Registering MCP {mcp_id} config: command={command}, args={args}, cwd={cwd}")
        
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        server_params = StdioServerParameters(
            command=command,
            args=args,
            cwd=cwd,
            env=full_env
        )
        self.server_configs[mcp_id] = server_params
        self.server_states[mcp_id] = {
            "status": "registered",
            "last_heartbeat": None,
            "last_error": None
        }
        
        logger.info(f"MCP config {mcp_id} registered successfully.")
        return {"mcp_id": mcp_id, "status": "registered"}

    async def terminate_mcp(self, mcp_id: str):
        """Removes an MCP server configuration."""
        if mcp_id in self.server_configs:
            logger.info(f"Removing MCP config {mcp_id}.")
            del self.server_configs[mcp_id]
            if mcp_id in self.server_states:
                del self.server_states[mcp_id]
        else:
            logger.warning(f"Attempted to terminate non-existent MCP config: {mcp_id}")

    async def get_mcp_status(self, mcp_id: str) -> dict:
        """Gets the detailed status of an MCP server."""
        return self.server_states.get(mcp_id, {"status": "not found"})

    async def list_mcp_tools(self, mcp_id: str) -> list[Tool]:
        """Requests the list of tools from an MCP server using its registered config."""
        server_params = self.server_configs.get(mcp_id)
        if not server_params:
            raise ValueError(f"MCP config for {mcp_id} not found. Register it first.")

        now = time.monotonic()
        cached = self._tools_cache.get(mcp_id)
        if cached and (now - float(cached["at"])) < self.tools_cache_ttl_s:
            return cached["tools"]

        lock = self._tools_locks.get(mcp_id)
        if lock is None:
            lock = asyncio.Lock()
            self._tools_locks[mcp_id] = lock

        async with lock:
            now = time.monotonic()
            cached = self._tools_cache.get(mcp_id)
            if cached and (now - float(cached["at"])) < self.tools_cache_ttl_s:
                return cached["tools"]
        
        self.server_states[mcp_id]["status"] = "listing_tools"
        
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await asyncio.wait_for(session.initialize(), timeout=10)
                    tools_data = await asyncio.wait_for(session.list_tools(), timeout=self.default_timeout)
                    
                    self.server_states[mcp_id]["status"] = "active"
                    self.server_states[mcp_id]["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
                    self.server_states[mcp_id]["last_error"] = None

                    tools = tools_data.tools
                    self._tools_cache[mcp_id] = {"at": time.monotonic(), "tools": tools}
                    return tools
        except Exception as e:
            logger.error(f"Error listing tools for MCP {mcp_id}: {str(e)}")
            self.server_states[mcp_id]["status"] = "error"
            self.server_states[mcp_id]["last_error"] = str(e)
            raise e

    async def call_mcp_tool(self, mcp_id: str, tool_name: str, tool_args: dict) -> dict:
        """Calls a specific tool on an MCP server using its registered config."""
        server_params = self.server_configs.get(mcp_id)
        if not server_params:
            raise ValueError(f"MCP config for {mcp_id} not found. Register it first.")
        
        self.server_states[mcp_id]["status"] = f"running_tool:{tool_name}"
        
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await asyncio.wait_for(session.initialize(), timeout=10)
                    result = await asyncio.wait_for(session.call_tool(tool_name, arguments=tool_args), timeout=self.default_timeout)
                    
                    self.server_states[mcp_id]["status"] = "active"
                    self.server_states[mcp_id]["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
                    self.server_states[mcp_id]["last_error"] = None
                    
                    return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on MCP {mcp_id}: {str(e)}")
            self.server_states[mcp_id]["status"] = "error"
            self.server_states[mcp_id]["last_error"] = str(e)
            raise e

    async def shutdown_all_mcps(self):
        """Removes all MCP server configurations."""
        mcp_ids = list(self.server_configs.keys())
        for mcp_id in mcp_ids:
            await self.terminate_mcp(mcp_id)
        self.server_configs.clear()
