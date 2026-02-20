# Next Session Handoff (2026-02-20)

## Current State
- Architecture refactor completed for major routers:
  - `backend/routers/platform.py` -> split into focused `platform_*` modules.
  - `backend/routers/messaging.py` -> split into focused `messaging_*` modules.
  - `backend/routers/ai_crm.py` -> split into focused `ai_crm_*` modules.
- Main entrypoint and lifecycle wiring were split:
  - `backend/main.py` is now thin composition.
  - Startup/shutdown orchestration moved to `backend/src/infra/lifecycle.py`.
  - Router registration moved to `backend/src/adapters/api/router_registry.py`.
- Architecture guardrails added:
  - `backend/tests/test_architecture_boundaries.py`.
  - `backend/tests/conftest.py` skips `*_live.py` by default unless `RUN_LIVE_TESTS=1`.

## Required Checks (Last Run)
- `cd backend && .venv/bin/python -m pytest -q` -> pass
- `cd backend && .venv/bin/python -m pytest -q tests/test_architecture_boundaries.py` -> pass

## Remaining Undone Tasks (Ordered)
1. Split oversized app file:
- `backend/src/app/background_tasks_inbound.py` is still 581 lines (> 500 hard limit).

2. Reduce remaining architecture debt (currently 18 violations):
- Prioritize `app/runtime/*` and background tasks.
- Remove allowlist entries only when true dependency violations are eliminated.

3. Increase `ports` usage:
- Introduce contracts to decouple app layer from concrete adapter/infra imports.

4. Test hardening:
- Add minimal non-live tests for critical messaging and AI CRM flows.
- Keep live suites opt-in (`RUN_LIVE_TESTS=1`).

5. Legacy cleanup:
- Reconcile/retire duplicate legacy paths (`backend/runtime/*`, `backend/policy/*`) after confirming no active imports.

## Current Boundary Violation Inventory (18)
- (`adapters/api/dependencies.py`, `adapters`, `domain`)
- (`adapters/api/dependencies.py`, `adapters`, `infra`)
- (`adapters/api/status_routes.py`, `adapters`, `infra`)
- (`adapters/db/tenant_models.py`, `adapters`, `domain`)
- (`adapters/db/user_models.py`, `adapters`, `domain`)
- (`app/background_tasks_ai_crm.py`, `app`, `infra`)
- (`app/background_tasks_inbound.py`, `app`, `infra`)
- (`app/background_tasks_inbound.py`, `app`, `adapters`)
- (`app/background_tasks_messaging.py`, `app`, `infra`)
- (`app/policy/evaluator.py`, `app`, `adapters`)
- (`app/runtime/agent_runtime.py`, `app`, `adapters`)
- (`app/runtime/agent_runtime.py`, `app`, `infra`)
- (`app/runtime/context_builder.py`, `app`, `adapters`)
- (`app/runtime/crm_agent.py`, `app`, `adapters`)
- (`app/runtime/knowledge_processor.py`, `app`, `infra`)
- (`app/runtime/memory_service.py`, `app`, `adapters`)
- (`app/runtime/memory_service.py`, `app`, `infra`)
- (`app/runtime/rag_service.py`, `app`, `adapters`)

## Resume Commands
```bash
cd backend
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q tests/test_architecture_boundaries.py
```

## Next Action Recommendation
- Start by splitting `backend/src/app/background_tasks_inbound.py` into:
  - queue intake/listen-notify module
  - inbound processing module
  - debug/introspection module
- While splitting, remove at least one `app -> adapters/infra` import and shrink allowlist accordingly.
