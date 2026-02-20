# Module Index

## Entry + Composition

- `backend/main.py`: thin FastAPI entrypoint and static frontend serving.
- `backend/src/adapters/api/router_registry.py`: centralized API router registration and dependency scopes.
- `backend/src/adapters/api/status_routes.py`: root/health/readiness endpoints.
- `backend/src/infra/lifecycle.py`: startup/shutdown orchestration and startup health state.
- `backend/routers/platform.py`: platform route composition root.
- `backend/routers/platform_identity_routes.py`: tenant/user/membership admin endpoints.
- `backend/routers/platform_audit_routes.py`: audit, security event, message history, and system health endpoints.
- `backend/routers/platform_llm_routes.py`: API key lifecycle and LLM routing/model/benchmark endpoints.
- `backend/routers/platform_settings_routes.py`: platform boolean setting endpoints.
- `backend/routers/platform_schemas.py`: shared request/response DTOs for platform endpoints.
- `backend/routers/platform_key_validation.py`: provider key validation helper functions.
- `backend/routers/messaging.py`: messaging composition router.
- `backend/routers/messaging_whatsapp_routes.py`: WhatsApp session lifecycle endpoints.
- `backend/routers/messaging_whatsapp_import_routes.py`: WhatsApp conversation import endpoint.
- `backend/routers/messaging_core_routes.py`: outbound/inbound/thread routes and dispatch endpoint.
- `backend/routers/messaging_mvp_routes.py`: operational checks/debug/simulation endpoints.
- `backend/routers/messaging_runtime.py`: shared runtime dispatch/LLM helper operations.
- `backend/routers/messaging_schemas.py`: shared request/response DTOs for messaging endpoints.
- `backend/routers/messaging_helpers.py`: compatibility facade for messaging helpers.
- `backend/routers/messaging_helpers_validation.py`: messaging validation and session/thread helpers.
- `backend/routers/messaging_helpers_payload.py`: messaging payload parsing and normalization helpers.
- `backend/routers/ai_crm.py`: AI CRM composition router + background cycle export.
- `backend/routers/ai_crm_routes.py`: AI CRM route handlers for control/threads/scan/trigger.
- `backend/routers/ai_crm_runtime.py`: AI CRM scan/trigger orchestration and background cycle logic.
- `backend/routers/ai_crm_helpers.py`: AI CRM helper/normalization/state helper logic.
- `backend/routers/ai_crm_schemas.py`: AI CRM API DTOs.

## App Layer

- `backend/src/app/background_tasks.py`: legacy CRM background loop placeholder (intentionally disabled).
- `backend/src/app/background_tasks_inbound.py`: inbound queue worker orchestration.
- `backend/src/app/background_tasks_messaging.py`: outbound dispatch orchestration.
- `backend/src/app/background_tasks_ai_crm.py`: AI CRM periodic orchestration.
- `backend/src/app/runtime/*`: runtime conversation/CRM orchestration services.
- `backend/src/app/policy/evaluator.py`: policy decision logic.

## Domain Layer

- `backend/src/domain/entities/enums.py`: core domain enums.

## Adapters Layer

- `backend/src/adapters/api/dependencies.py`: auth/provider dependency factories.
- `backend/src/adapters/db/*.py`: SQLModel persistence models by bounded context.
- `backend/src/adapters/mcp/manager.py`: MCP process orchestration.
- `backend/src/adapters/zai/client.py`: provider client adapter.

## Infra Layer

- `backend/src/infra/database.py`: SQLModel engine/session.
- `backend/src/infra/migrations.py`: additive migration routines.
- `backend/src/infra/seeding.py`: startup baseline seed routines.
- `backend/src/infra/schema_checks.py`: runtime schema compatibility checks.
- `backend/src/infra/security.py`: auth/security primitives.
- `backend/src/infra/llm/*`: LLM provider/router infrastructure.

## Shared Layer

- `backend/src/shared/exceptions.py`: shared exception primitives.

## Architecture Guardrails

- `backend/tests/test_architecture_boundaries.py`: fails on newly introduced cross-layer import violations.
