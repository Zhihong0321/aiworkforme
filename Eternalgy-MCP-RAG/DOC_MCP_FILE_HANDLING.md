# MCP and File Handling Documentation

## Overview
The project integrates the **Model Context Protocol (MCP)** to give AI agents access to external tools. Uniquely, it employs a **Hybrid Architecture** that combines standard process-based MCP servers with optimized, in-process tools (specifically for Billing).

## 1. MCP Architecture

### Standard MCP Servers
*   **Manager**: `backend/app/core/mcp_manager.py` manages external processes (start/stop/health).
*   **Execution**: Tools are executed via `subprocess` communication with independent scripts (e.g., `mcp_file_server.py`).
*   **Registry**: `mcp_servers` database table stores configuration (Command, Args, Env).
*   **API Management**: `backend/app/api/mcp.py` provides REST endpoints to create, update, and control these servers.

### Special Case: Hardcoded Billing Tools
**WARNING**: The codebase contains hardcoded logic for Billing tools that bypasses the standard MCP process.
*   **Location**: `backend/app/api/chat.py`
*   **Tools**: `tnb_bill_rm_to_kwh`, `tnb_bill_kwh_to_rm`, `calculate_solar_impact`.
*   **Implementation**: These are defined in `_billing_tools()` and executed **in-process** via `_execute_billing_tool()` reading a local `bill.json`.
*   **Trigger**: If an agent has no specific MCP servers assigned, the system **automatically falls back** to enabling these billing tools.

## 2. Implementing a New MCP Server
To add a new tool capability (e.g., "Git Integration"), follow this standard pattern:

### Step 1: Create the Server Script
Write a Python script (e.g., `mcp_git_server.py`) using the `mcp` SDK.
*   **Protocol**: Must use `stdio_server` for communication.
*   **Decorators**: Use `@server.list_tools()` and `@server.call_tool()`.
*   **Output**: Tools must return `List[TextContent]`.
*   **Logging**: Print debug info to `stderr` (stdout is reserved for JSON-RPC).

```python
# Minimal Example
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("my-new-server")

@server.list_tools()
async def list_tools():
    return [Tool(name="my_tool", ...)]

@server.call_tool()
async def call_tool(name, arguments):
    return [TextContent(type="text", text="Result")]

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 2: Register via API
Use `POST /api/v1/mcp/servers` to register the script.
*   **Command**: `python`
*   **Arguments**: `["/app/mcp_git_server.py"]` (Use absolute paths or relative to working_dir).
*   **Working Directory**: `/app` (or specific project root).

## 3. Linking Agents to MCPs

### Database Model
The relation is Many-to-Many, managed by the `agent_mcp_servers` table:
*   `agent_id` (Integer)
*   `server_id` (String UUID)
*   `is_enabled` (Boolean)

### Management API (`backend/app/api/agents.py`)
*   **Create/Update Agent**: Endpoints accept a list of `mcp_servers` (IDs).
*   **Sync Logic**: `_sync_agent_mcp_servers` helper function clears old associations and inserts new ones.

### Runtime Discovery
1.  Chat request initiates.
2.  System fetches linked servers via `_get_agent_mcp_servers`.
3.  **Fallback Rule**: If no servers are linked, it looks for any enabled server with "billing" in the name.
4.  Tools from all identified servers are aggregated and sent to the Z.ai API.

## 4. File Handling Modes

### Mode A: Knowledge Base (RAG-lite)
*   **Purpose**: Background context (PDFs, Docs).
*   **Flow**:
    1.  **Upload**: `POST /{agent_id}/upload`.
    2.  **External Sync**: Files are uploaded to Z.ai's file storage (`upload_file_to_zai`).
    3.  **Database**: Metadata stored in `agent_knowledge_files`.
    4.  **Injection**: Content is appended to the **System Prompt** during chat.

### Mode B: Active File Tools (MCP)
*   **Purpose**: Agent-driven file manipulation (Coding).
*   **Component**: `mcp_file_server.py`.
*   **Key Tools**: `read_file`, `list_files`, `search_code`.
*   **Security**: Restricted to specific allowed paths defined in the server script.

## 5. Metrics & Logging
*   **`mcp_tool_usage`**: Tracks every tool execution, arguments, response, and duration (ms).
*   **`mcp_server_logs`**: Captures stderr/stdout from external MCP processes for debugging.

## Summary
*   **Hybrid Dispatch**: Standard MCP (Process) + Optimized Billing (In-Process).
*   **Implementation**: Scripts must use `mcp.server.stdio`.
*   **Registration**: Via `POST /api/v1/mcp/servers`.
*   **Dual File System**: Z.ai-hosted Knowledge Base + Local File System Access.
