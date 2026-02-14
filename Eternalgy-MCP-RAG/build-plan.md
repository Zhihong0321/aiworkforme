# Build Plan: Z.ai Chatbot System (Light TUI Edition)

## 1. System Architecture

### General
*   **Root URL (`/`)**: Serves the Admin Dashboard (React frontend).
*   **API Root (`/api/v1`)**: All backend APIs will be exposed under this prefix.

### Backend (Python/FastAPI)
*   **Framework**: FastAPI for high-performance async API.
*   **Database**: PostgreSQL with SQLModel (SQLAlchemy) for ORM.
*   **AI Engine**: Custom Z.ai Client (handling Coding Plan specifics).
*   **MCP Engine**: Subprocess manager for executing local MCP servers.

### Frontend (Vue.js/Vite)
*   **Theme**: "Light TUI" (Terminal User Interface).
    *   White/Light Gray Background (`#f0f0f0` or similar).
    *   Dark Text (`#1a1a1a`).
    *   Monospace Fonts (Fira Code, JetBrains Mono, or Courier).
    *   Block Cursors, strict borders, "retro" interactive elements.
*   **Routing**: Vue Router.
*   **State**: TanStack Query (Vue Query) or Pinia for API sync.

## 2. Implementation Steps

### Phase 0: UI/UX Prototyping (UI 1st)
1.  **Design System**:
    *   Create "Terminal" components: `Window`, `Prompt`, `Button` (text-based style), `Table`.
    *   Apply "Light Theme" variables.
2.  **Page Scaffolding (No Functionality)**:
    *   Create placeholder pages for the main sections of the Admin Dashboard.
    *   Implement routing to allow browsing between these pages.
    *   **Agent Management**: List, Create, Edit (System Prompt, Model).
    *   **MCP Management**: Upload scripts, configure env vars, link to Agents.
    *   **Tester Chat**:
        *   Split pane: Chat History vs Reasoning Log (Terminal style).
        *   Static or mock data for display.

### Phase 1: Backend Scaffolding & Core
1.  **Setup**: Initialize `backend/` directory, `pyproject.toml` (or `requirements.txt`).
2.  **Database**:
    *   Define models: `Agent`, `ChatSession`, `ChatMessage`, `MCPServer`, `AgentMCPServer`.
    *   Setup migrations (Alembic).
3.  **Z.ai Integration**:
    *   Implement `ZaiClient` with `httpx` (300s timeout).
    *   Implement `reasoning_content` fallback logic.
    *   Setup Base URL: `https://api.z.ai/api/coding/paas/v4`.

### Phase 2: MCP Implementation
1.  **MCP Manager**:
    *   Create `MCPManager` class to spawn/monitor subprocesses.
    *   Implement `stdio` communication (JSON-RPC).
    *   Handle `stderr` logging constraints.
2.  **MCP CRUD**:
    *   API endpoints to Create/Update/Delete MCP server configurations.
    *   Upload mechanism for script files.
3.  **Agent Integration**:
    *   Update Agent Chat flow to inject available Tools from linked MCPs.

### Phase 3: Frontend-Backend Integration
1.  **Connect UI to API**:
    *   Replace mock data with actual API calls using TanStack Query.
    *   Implement streaming output display for the Tester Chat.

### Phase 4: Integration & Verification
1.  **Tester Page**: Ensure "Generate Tester Page" works (likely a dynamic route `/test/:agent_id`).
2.  **E2E Test**:
    *   Create Agent.
    *   Upload MCP (e.g., simple file tool).
    *   Link MCP to Agent.
    *   Chat and verify Tool Usage + Reasoning display.

## 3. Tech Stack Details

*   **Language**: Python 3.12+
*   **Dependencies**: `fastapi`, `uvicorn`, `sqlmodel`, `httpx`, `openai` (for protocol compatibility), `alembic`, `psycopg2-binary`.
*   **Frontend**: `Vue.js`, `TailwindCSS` (for easier TUI styling), `lucide-vue` (icons).

## 4. Specific Constraints Checklist
*   [ ] **Timeout**: Set Z.ai client timeout to 300s.
*   [ ] **URL**: Use `api.z.ai/api/coding/paas/v4`.
*   [ ] **Logs**: Surface MCP `stderr` to UI/Logs.
*   [ ] **Theme**: STRICTLY Light Mode TUI (No dark mode defaults).
