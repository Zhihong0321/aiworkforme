# Frontend Build Plan

## Scope & Assumptions
- UI only; no backend edits. Consume existing `/api/v1` endpoints under `http://localhost:8001/api/v1`.
- App launches at `/` to the Admin Dashboard (home).
- Product: RAG Agent Management with sections for Dashboard, Agents, MCPs, Threads.

## Routes & Layout
1) `/` Admin Dashboard (default).  
2) `/agents` Agent Management (list + detail/edit + create).  
3) `/mcps` MCP Management (list + detail).  
4) `/threads` Thread Management (list + detail).  
5) `/chat` Chat interface (agent selection + conversation) per guide.

Shared layout: top nav with section links + global status; responsive grid using TUI style (uppercase labels, tight tracking).

## Data Needs (frontend contract)
- Agents: `id`, `name`, `model`, `system_prompt`, `status`, `lastActive`, `tokenCountToday`, `linkedMcpId`, `files[]`.
- MCP servers: `id`, `name`, `status`, `endpoint`, `capabilities`.
- Threads: `id`, `agentId`, `title/preview`, `lastActive`, `tokensUsed`, `status`; need last 10 active for dashboard.
- Stats: agent status summary, token totals today, counts (agents, MCPs, active threads).

## Dashboard (Home)
- Hero: RAG Agent overview + “Create Agent” CTA.
- Widgets:
  - Last 10 active threads (title, agent, last active, tokens).
  - Agent status summary (per agent: lastActive, tokenCountToday; quick state badge).
  - High-level metrics (total agents, total MCPs, active threads).
  - API hint: surface `/api/v1` base for discoverability.
- Data source: `GET /agents/` and `GET /threads?limit=10&status=active` (or filtered client-side until backend provides filter).

## Agent Management
- List: searchable/sortable table (name, model, linked MCP, status, lastActive, tokenCountToday) from `GET /agents/`.
- Detail/Edit:
  - Fields: name, system_prompt/instruction (textarea), model select, linked MCP select, file attachments list, status badge.
  - Actions: save/update via `POST /agents/` or `PUT /agents/{id}`, link MCP via `POST /agents/{id}/link-mcp/{serverId}`, upload knowledge via `POST /agents/{id}/knowledge` (FormData `file`), remove attachment (UI stub until endpoint).
- “Create Agent” uses same form with empty defaults.

## MCP Management
- List: MCP servers from `GET /mcp/servers` (or placeholder + request backend if missing).
- Detail: server info + linked agents; UI control to refresh status (client-only until endpoint).

## Thread Management
- List: threads with agent, lastActive, tokensUsed, status; filter by agent/status; source `/threads` once available or mock until endpoint exposed.
- Detail: messages/log preview (mock data if needed), metadata, actions (archive/end thread UI).

## Chat View
- Agent selector (from `GET /agents/`), message list, composer.
- Send flow: push user message, call `POST /chat/` with `{ agent_id, message }`, show loader, render response.

## Components to Build
- Status badges (fixed width where needed), cards, tables/lists, TUI-styled section headers.
- Agent form (name, system_prompt, model select, MCP select, file list with upload control).
- Thread list item component (compact for dashboard widget).
- Chat message bubble/log with loader state.
- Layout: Nav, PageShell, section wrappers honoring TUI typography (uppercase, tracking).

## API Integration Stubs (Base: `http://localhost:8001/api/v1`)
- `GET /agents/` (list), `POST /agents/` (create), `PUT /agents/{id}` (update), `POST /agents/{id}/link-mcp/{serverId}`, `POST /agents/{id}/knowledge` (FormData file).
- `GET /mcp/servers` (list; confirm availability) and `POST /mcp/servers`.
- `GET /threads` (list, support limit/status when available).
- `POST /chat/` (agent_id, message).

## Phased Implementation
1) Routing/layout shell with nav + top-level pages + `/chat`.  
2) Dashboard widgets with mock data, then wire to `/agents/` and `/threads` once available.  
3) Agent list + detail/create form (instruction/system_prompt, model, MCP link, file upload UI).  
4) MCP list/detail views.  
5) Thread list/detail views.  
6) Chat view wired to `/chat/`.  
7) Replace remaining mocks with API service layer pointing to `http://localhost:8001/api/v1`.  
8) Polish: responsiveness, empty/loading states, accessibility, TUI typography/spacing.

## Testing & Validation
- Component-level checks: forms render, lists handle empty/loading, chat send flow shows loader.
- View smoke tests via manual run `npm run dev` / `npm run build` in `frontend`.
