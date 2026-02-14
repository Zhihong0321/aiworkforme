# Frontend Implementation & Integration Guide

## 1. Introduction
This document serves as the primary reference for the frontend team to build the Z.ai Chatbot UI. It outlines the technology stack, backend API structure, and specific instructions for wiring the UI to the backend services.

## 2. Tech Stack & Environment
-   **Framework**: Vue 3 (Composition API, `<script setup>`)
-   **Build Tool**: Vite
-   **Styling**: Tailwind CSS (with custom TUI-inspired components in `src/components/ui`)
-   **State Management**: Reactivity API (`ref`, `reactive`)
-   **HTTP Client**: Native `fetch` (or install `axios` if preferred)

### Local Development
The frontend interacts with the backend running on `http://localhost:8001`.
Ensure the backend is running via Docker or locally before testing.

## 3. Backend Integration Points
**Base URL**: `http://localhost:8001/api/v1`

### 3.1 Agents (`/agents`)
-   **List Agents**: `GET /agents/`
    -   *Returns*: Array of Agent objects `{id, name, model, system_prompt, ...}`
-   **Create Agent**: `POST /agents/`
    -   *Body*: `{ "name": "...", "model": "glm-4.5-flash", "system_prompt": "..." }`
-   **Link MCP**: `POST /agents/{agent_id}/link-mcp/{server_id}`
-   **Upload Knowledge**: `POST /agents/{agent_id}/knowledge`
    -   *Body*: `FormData` with file field `file`.

### 3.2 MCP Servers (`/mcp`)
-   **List Servers**: `GET /mcp/servers` (You may need to implement this endpoint in backend if missing, or use `mcp_manager` status)
    -   *Note*: Currently, the backend exposes `POST /mcp/servers` to create. You might need to add a listing endpoint or query the DB directly if only for admin. *Action Item*: Request a "List MCP Servers" endpoint if not found.
-   **Create Server**: `POST /mcp/servers`
    -   *Body*: `{ "name": "...", "script": "/app/path/to/script.py", "env_vars": "{}" }`

### 3.3 Chat (`/chat`)
-   **Send Message**: `POST /chat/`
    -   *Body*: `{ "agent_id": 1, "message": "Hello world" }`
    -   *Response*: `{ "response": "AI reply here..." }`
    -   *Note*: The backend handles tool execution internally. The response is the final text.

## 4. Feature Implementation Strategy

### 4.1 Dashboard Refactor (`src/views/Dashboard.vue`)
The current dashboard uses mock data (`const agents = [...]`). This needs to be replaced with real data fetching.

**Step 1: Fetch Agents**
```javascript
import { ref, onMounted } from 'vue'

const agents = ref([])
const isLoading = ref(true)

const fetchAgents = async () => {
  try {
    const res = await fetch('http://localhost:8001/api/v1/agents/')
    agents.value = await res.json()
  } catch (e) {
    console.error('Failed to load agents', e)
  } finally {
    isLoading.value = false
  }
}

onMounted(fetchAgents)
```

**Step 2: Map Data to UI**
Update the `v-for="agent in agents"` loop to use the real properties from the API (`agent.name`, `agent.model`). You may need to compute mock values for `status`, `tokens`, `latency` until the backend provides real metrics.

### 4.2 New Feature: Agent Creator
Create a new view or modal to POST to `/api/v1/agents/`.
-   Use `TuiInput` for Name and System Prompt.
-   Use a standard `<select>` or `TuiSelect` (if available) for Model selection.

### 4.3 New Feature: Chat Interface
A dedicated Chat View is required.
1.  **Select Agent**: User picks an agent from the list.
2.  **Chat History**: Maintain a local array `messages = ref([])`.
3.  **Send**:
    -   Push user message to local array.
    -   Call `POST /chat/`.
    -   Show loading state (breathing cursor or loader).
    -   Push assistant response to local array.

### 4.4 New Feature: File Upload (RAG)
Add a "Knowledge Base" section to the Agent details.
-   **Input**: `<input type="file" @change="handleUpload">`
-   **Handler**:
```javascript
const uploadFile = async (agentId, file) => {
  const formData = new FormData()
  formData.append('file', file)
  
  await fetch(`http://localhost:8001/api/v1/agents/${agentId}/knowledge`, {
    method: 'POST',
    body: formData
  })
}
```

## 5. UI Components & Styling
-   **Tui Components**: Located in `src/components/ui`. Use them to maintain the "Light TUI" aesthetic.
-   **Breathing Effects**: `TuiInput` has a `breathing-ring` class. Reuse this logic for other interactive elements if desired.
-   **Typography**: The design relies heavily on uppercase tracking (`tracking-widest`) and small font sizes (`text-xs`) for labels.

## 6. Docker & Deployment
-   The `frontend/Dockerfile` is set up for production (Nginx).
-   For local dev, `npm run dev` in `frontend/` directory is sufficient.
-   Ensure CORS is configured in Backend `main.py` if running frontend on a different port than `8080` (Backend currently allows `http://localhost:8080`).

## 7. Action Items for Frontend Team
1.  [ ] **Connect Dashboard**: Replace mock agent list with `GET /agents`.
2.  [ ] **Create Agent Form**: Implement UI to create new agents.
3.  [ ] **Chat View**: Build the main chat interface.
4.  [ ] **MCP & Files**: Add UI controls for linking MCP servers and uploading files.
