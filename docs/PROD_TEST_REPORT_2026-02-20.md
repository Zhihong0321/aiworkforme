# Production Test Report (2026-02-20)

## Scope
- Target environment: `https://aiworkforme-production.up.railway.app`
- Test account: tenant user (`2@2.com`)
- Test mode: read + write API smoke, with cleanup where supported
- Run window (UTC): `2026-02-20T08:31:05` to `2026-02-20T08:31:08`

## Summary
- Total checks: **18**
- Passed: **16**
- Failed: **2**

## Passed Tests
1. `POST /api/v1/auth/login` -> `200`
2. `GET /api/v1/` -> `200`
3. `GET /api/v1/health` -> `200`
4. `GET /api/v1/ready` -> `200`
5. `GET /api/v1/workspaces/` -> `200`
6. `GET /api/v1/agents/` -> `200`
7. `GET /api/v1/mcp/servers` -> `200`
8. `GET /api/v1/analytics/summary?window_hours=24` -> `200`
9. `GET /api/v1/messaging/mvp/operational-check` -> `200`
10. `GET /api/v1/messaging/mvp/inbound-health` -> `200`
11. `GET /api/v1/platform/tenants` as tenant user -> `403` (expected)
12. `POST /api/v1/workspaces/{id}/leads` -> `200`
13. `POST /api/v1/workspaces/{id}/leads/{lead_id}/mode` -> `200`
14. `POST /api/v1/mcp/servers` (with `tenant_id` in body) -> `200`
15. `DELETE /api/v1/workspaces/{id}/leads/{lead_id}` -> `200`
16. `DELETE /api/v1/mcp/servers/{id}` -> `200`

## Failed Tests
1. `POST /api/v1/agents/` -> `500 Internal Server Error`
2. `POST /api/v1/mcp/servers` (without `tenant_id` in body) -> `500 Internal Server Error`

## Observations
- Core health/read paths are stable.
- Lead write flow is working end-to-end.
- Agent create endpoint is currently broken in production (`500`).
- MCP create endpoint works only when `tenant_id` is explicitly included in payload; without it, server returns `500` instead of a validation/authorization error.

## Data Side Effects
- Cleanup succeeded for artifacts from final run (`lead_id=17`, `mcp_id=8`).
- One test workspace remains from an earlier run:
  - `workspace_id=2`, name like `ProdTest-WS-...`
  - No delete endpoint exists for workspace in current API, so it was not removed.

## Next-Step Patch Tasks
1. Fix `POST /api/v1/agents/` server error.
- File: `backend/routers/agents.py`
- Actions:
  - Reproduce with same payload used by frontend (`name`, `system_prompt`).
  - Inspect server logs/traceback for exact failure point.
  - Add defensive validation and explicit `4xx` responses where appropriate.
  - Add/expand non-live test covering successful agent create.

2. Fix `POST /api/v1/mcp/servers` tenant handling.
- File: `backend/routers/mcp.py`
- Actions:
  - Set `server.tenant_id = auth.tenant.id` from auth context instead of requiring client payload.
  - Update route signature to require tenant auth context for create path.
  - Return explicit `400/403` for malformed/unauthorized requests rather than `500`.
  - Add non-live test for create with and without tenant_id in payload to ensure robust behavior.

3. Add production-safe smoke test script in repo.
- Suggested file: `backend/tests/smoke_prod_manual.py` (not in default pytest run).
- Actions:
  - Include read + write + cleanup sequence.
  - Print pass/fail per endpoint.
  - Keep credential/base URL from env vars only.

4. Optional API hygiene.
- Add workspace delete endpoint if intended, or document that workspaces are immutable once created.
- If immutable, add admin cleanup path to avoid test artifact accumulation.

## Recommended Re-test After Patch
1. `POST /api/v1/agents/` should return `200` and create agent.
2. `POST /api/v1/mcp/servers` without payload `tenant_id` should still return `200` (tenant derived from auth).
3. Repeat full read + write smoke and verify cleanup completes.
