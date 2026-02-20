# Refactor Changelog (2026-02-20)

## File Moves / Responsibility Moves

- Startup and shutdown orchestration moved from `backend/main.py` to `backend/src/infra/lifecycle.py`.
- API router include orchestration moved from `backend/main.py` to `backend/src/adapters/api/router_registry.py`.
- Status endpoints (`/api/v1/`, `/api/v1/health`, `/api/v1/ready`) moved from `backend/main.py` to `backend/src/adapters/api/status_routes.py`.
- Platform admin endpoints were split from `backend/routers/platform.py` into focused modules:
- Identity administration -> `backend/routers/platform_identity_routes.py`
- Audit/health visibility -> `backend/routers/platform_audit_routes.py`
- Provider key + LLM control -> `backend/routers/platform_llm_routes.py`
- Platform boolean settings -> `backend/routers/platform_settings_routes.py`
- Shared DTOs/helpers -> `backend/routers/platform_schemas.py`, `backend/routers/platform_key_validation.py`
- Messaging router concerns were partially extracted from `backend/routers/messaging.py`:
- Messaging router was split into focused modules:
- Router composition -> `backend/routers/messaging.py`
- WhatsApp session lifecycle routes -> `backend/routers/messaging_whatsapp_routes.py`
- WhatsApp import route -> `backend/routers/messaging_whatsapp_import_routes.py`
- Core inbound/outbound/thread routes -> `backend/routers/messaging_core_routes.py`
- MVP diagnostics/simulation routes -> `backend/routers/messaging_mvp_routes.py`
- Runtime operations -> `backend/routers/messaging_runtime.py`
- Messaging DTOs -> `backend/routers/messaging_schemas.py`
- Messaging helper logic -> `backend/routers/messaging_helpers_validation.py`, `backend/routers/messaging_helpers_payload.py`
- Compatibility facade -> `backend/routers/messaging_helpers.py`
- AI CRM router was split into focused modules:
- Router composition -> `backend/routers/ai_crm.py`
- Route handlers -> `backend/routers/ai_crm_routes.py`
- Runtime orchestration -> `backend/routers/ai_crm_runtime.py`
- Helper logic -> `backend/routers/ai_crm_helpers.py`
- DTOs -> `backend/routers/ai_crm_schemas.py`

## Files Added

- `backend/src/adapters/api/router_registry.py`
- `backend/src/adapters/api/status_routes.py`
- `backend/src/infra/lifecycle.py`
- `backend/src/README.md`
- `backend/src/app/README.md`
- `backend/src/domain/README.md`
- `backend/src/ports/README.md`
- `backend/src/adapters/README.md`
- `backend/src/infra/README.md`
- `backend/src/shared/README.md`
- `backend/tests/test_architecture_boundaries.py`
- `backend/routers/platform_schemas.py`
- `backend/routers/platform_key_validation.py`
- `backend/routers/platform_identity_routes.py`
- `backend/routers/platform_audit_routes.py`
- `backend/routers/platform_llm_routes.py`
- `backend/routers/platform_settings_routes.py`
- `backend/routers/README.md`
- `backend/routers/messaging_schemas.py`
- `backend/routers/messaging_helpers.py`
- `backend/routers/messaging_runtime.py`
- `backend/routers/messaging_whatsapp_routes.py`
- `backend/routers/messaging_whatsapp_import_routes.py`
- `backend/routers/messaging_core_routes.py`
- `backend/routers/messaging_mvp_routes.py`
- `backend/routers/messaging_helpers_validation.py`
- `backend/routers/messaging_helpers_payload.py`
- `backend/routers/ai_crm_schemas.py`
- `backend/routers/ai_crm_helpers.py`
- `backend/routers/ai_crm_runtime.py`
- `backend/routers/ai_crm_routes.py`

## Files Updated

- `backend/main.py` (thinned to framework composition)
- `backend/pyproject.toml` (pytest + ruff quality gates)
- `docs/ARCHITECTURE.md`
- `docs/CONTRIBUTING.md`
- `docs/DECISIONS.md`
- `docs/MODULE_INDEX.md`
- `backend/routers/platform.py` (now thin composition module)
- `backend/routers/messaging.py` (now thin composition module)
- `backend/routers/ai_crm.py` (now thin composition module)

## Behavior Change

- Intended external behavior: unchanged.
- Endpoint paths and startup sequencing remain equivalent.

## Incremental Boundary Debt Reduction

- Removed `app -> adapters` violation from `backend/src/app/background_tasks.py` by deleting unreachable legacy imports/code while preserving disabled behavior.
- Removed `app -> adapters` violation from `backend/src/app/background_tasks_messaging.py` by moving queued-tenant lookup behind `routers.messaging` runtime export.
- Removed `app -> adapters` violation from `backend/src/app/background_tasks_ai_crm.py` by obtaining default LLM router through `routers.ai_crm` composition export.
- Updated architecture allowlist in `backend/tests/test_architecture_boundaries.py` accordingly.
