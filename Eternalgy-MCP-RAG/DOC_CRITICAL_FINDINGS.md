# Critical Findings & Hidden Constraints

## Overview
This document contains "hidden" details and critical constraints discovered in the codebase that are not obvious from standard documentation. **Failure to observe these will likely break the system.**

## 1. Z.ai Cloud File Uploads (Critical)
The "Knowledge Base" feature is **NOT** purely local RAG.
*   **Mechanism**: Files uploaded via `POST /{agent_id}/upload` are sent to Z.ai's **Main API** (`https://api.z.ai/api/paas/v4/files`), NOT the Coding Plan API.
*   **Endpoint**: `https://api.z.ai/api/paas/v4/files` (Requires balance/credits if not covered by plan).
*   **Expiration**: The code hardcodes an 180-day expiration date for these files.
*   **Purpose Field**: Must be set to `'agent'`.
*   **Implementation**: See `upload_file_to_zai` in `backend/app/crud/crud.py`.

## 2. Hardcoded Billing Tools (Hidden Logic)
*   **Bypass**: If an agent has **NO** MCP servers assigned, the system automatically enables a set of hardcoded "Billing Tools" (`tnb_bill_rm_to_kwh`, etc.).
*   **Location**: `backend/app/api/chat.py` -> `_billing_tools()` and `_dispatch_tool()`.
*   **Dependency**: Requires a local file `bill.json` to exist in `backend/app/resource/` or `mcp_servers/billing_server/`. If missing, these tools fail silently or return "out_of_scope".

## 3. Database & Deployment Quirks
*   **Railway Postgres**: The system is designed to run on Railway. It expects `DATABASE_URL` to be auto-injected.
*   **Railway Build**: Railway no longer uses Nixpacks for this project; builds run from the Dockerfile (or your own CI) and `nixpacks.toml` is ignored. Keep the Docker image pipeline up to date when changing backend/frontend build steps.
*   **Procfile**: The web command `web: cd backend && python main.py` assumes the backend is the root context.
*   **Lazy Loading**: The CRUD operations (`crud.py`) explicitly avoid eager loading in `get_chat_sessions` to prevent SQL errors, implying potential performance or permission issues with the database schema.

## 4. MCP Implementation Constraints
*   **Protocol**: New MCP servers **MUST** use the `stdio_server` (standard input/output) protocol.
*   **Logging**: All debug logs from MCP servers **MUST** go to `stderr`. Anything printed to `stdout` will break the JSON-RPC communication and crash the tool.
*   **Working Directory**: The `mcp_manager` strictly enforces path resolution. All file operations must be relative to the server's configured `working_directory`. Absolute paths are rejected.

## 5. Frontend Assumptions
*   **Types**: The frontend expects a specific `Agent` interface that includes `mcp_servers` as an array of strings (IDs).
*   **Message Structure**: The frontend handles `reasoning_content` and `tools_used` fields. If the backend schema changes these names, the UI will break.

## 6. HTTP Client Timeouts
*   **Reasoning Models**: The Z.ai Coding API is slow when generating reasoning. The `httpx` client in `zai_client.py` is manually configured with a **300-second timeout**. Using a standard `openai.Client` without this custom `http_client` will result in frequent timeouts.
