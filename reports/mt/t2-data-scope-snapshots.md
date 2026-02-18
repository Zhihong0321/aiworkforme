# T2 Data Scope Snapshots
Date: 2026-02-16
Status: PASS

## Command
`docker compose exec backend sh -lc 'cd /app && pytest -q tests/test_role_matrix_live.py::test_cross_tenant_idor_is_blocked tests/test_m4_boundary_live.py::test_chat_session_message_idor_is_blocked tests/test_m4_boundary_live.py::test_workspace_update_idor_is_blocked tests/test_idor_extended_live.py'`

## Snapshot Highlights
- Tenant A reading Tenant B workspace leads: `GET /api/v1/workspaces/{workspace_b}/leads` -> `404`
- Tenant A updating Tenant B workspace: `PUT /api/v1/workspaces/{workspace_b}` -> `404`
- Tenant A updating Tenant B agent: `PUT /api/v1/agents/{agent_b}` -> `404`
- Tenant A reading Tenant B legacy chat session messages: `GET /api/v1/chat/{session_b}/messages` -> `404`
- Tenant A manipulating Tenant B MCP server:
  - `GET /api/v1/mcp/servers/{id}/status` -> `404`
  - `POST /api/v1/mcp/servers/{id}/start` -> `404`
  - `DELETE /api/v1/mcp/servers/{id}` -> `404`
- Tenant A accessing Tenant B knowledge resources:
  - `GET /api/v1/agents/{agent_b}/knowledge` -> `404`
  - `PATCH /api/v1/knowledge/{file_b}` -> `404`
- Tenant A on Tenant B playground/policy paths:
  - `GET /api/v1/workspaces/{workspace_b}/policy/decisions` -> `404`
  - `POST /api/v1/playground/chat?lead_id={lead_b}&workspace_id={workspace_b}` -> `404`

## Leakage Result
- Cross-tenant read leakage observed: `0`
- Cross-tenant write leakage observed: `0`
