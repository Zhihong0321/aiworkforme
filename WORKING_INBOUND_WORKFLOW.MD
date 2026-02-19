# WORKING INBOUND WORKFLOW

Last updated: 2026-02-19  
Status: Known working reference after inbound recovery and schema/readiness hardening.

## Purpose

This document is the source of truth for the **currently working inbound message processing path**.  
If future changes break inbound, use this workflow and checklist to compare behavior and restore service.

## High-Level Flow

1. Channel provider writes inbound message into `et_messages` (`direction='inbound'`, `delivery_status='received'`).
2. DB trigger assigns/creates thread and emits PostgreSQL notify event.
3. `background_inbound_worker_loop` claims message atomically (`received -> inbound_processing`).
4. Worker resolves tenant/lead/workspace/agent and builds thread history.
5. Worker runs `ConversationAgentRuntime.run_turn(...)`.
6. Runtime builds context, calls LLM router, performs policy checks, returns AI reply + trace metadata.
7. Worker writes outbound AI message into `et_messages` (`direction='outbound'`) + enqueue row in `et_outbound_queue`.
8. Outbound dispatcher sends the queued message through channel provider and updates delivery status.

## Canonical Components

- Inbound worker: `backend/src/app/background_tasks_inbound.py`
- Runtime orchestration: `backend/src/app/runtime/agent_runtime.py`
- Context assembly: `backend/src/app/runtime/context_builder.py`
- Unified messaging API + outbound dispatch: `backend/routers/messaging.py`
- LLM router/providers:
  - `backend/src/infra/llm/router.py`
  - `backend/src/infra/llm/providers/uniapi.py`
  - `backend/src/infra/llm/providers/zai.py`
- Startup migrations/readiness:
  - `backend/main.py`
  - `backend/src/infra/migrations.py`
  - `backend/src/infra/schema_checks.py`

## Required Data Contracts

### `et_messages` (must include)

- Core: `id`, `tenant_id`, `lead_id`, `thread_id`, `channel`, `direction`, `text_content`, `raw_payload`, `delivery_status`, `created_at`, `updated_at`
- LLM usage columns:
  - `llm_provider`
  - `llm_model`
  - `llm_prompt_tokens`
  - `llm_completion_tokens`
  - `llm_total_tokens`
  - `llm_estimated_cost_usd`

### AI Trace JSON (`raw_payload.ai_trace`)

For AI-generated outbound rows, trace is stored in strict JSON format:

```json
{
  "schema_version": "1.0",
  "task": "conversation",
  "provider": "uniapi",
  "model": "gemini-3-flash-preview",
  "usage": {
    "prompt_tokens": 123,
    "completion_tokens": 45,
    "total_tokens": 168,
    "raw_usage": {},
    "estimated_cost_usd": 0.000123
  },
  "context_prompt": "....",
  "recorded_at": "2026-02-19T14:00:00.000000"
}
```

`context_prompt` is populated only when platform setting `record_context_prompt=true`.

## Routing/Provider Behavior

- Default provider routing is **UniAPI for all tasks**.
- Z.ai remains fallback.
- Routing source:
  - In-memory default in dependencies.
  - Can be overridden by DB setting `llm_routing_config`.

## Worker and Delivery Status Lifecycle

Inbound status transitions:

- `received`
- `inbound_processing`
- `inbound_ai_replied` (success path)
- `inbound_human_takeover` (no agent/policy block/manual route)
- `inbound_error` (runtime failure)

Outbound queue status (typical):

- `queued`
- `processing`
- `sent` / `accepted`
- retry path: `retry_scheduled` -> `queued` (until max retry)
- terminal fail: `failed`

## Startup/Readiness Safety (Critical)

Startup performs:

1. SQLModel table creation.
2. Additive migrations.
3. Message usage columns migration (pre-SQL file).
4. SQL migration file apply (`messaging_m1_unified_schema.sql`) with fallback safety.
5. Message usage columns migration re-run.
6. Schema compatibility check.

Readiness endpoint `/api/v1/ready` returns 503 if schema compatibility fails.

## Permanent Health/Diagnostics

Platform admin endpoint:

- `GET /api/v1/platform/system-health`

Includes:

- schema compatibility result (`et_messages` required columns)
- inbound worker debug snapshot
- LLM provider health
- blockers list + global ready flag

Platform admin UI:

- `Settings` page includes:
  - Platform System Health panel
  - Platform Message History (with AI trace and LLM usage fields)

## Configuration Checklist (Must-Have)

- `DATABASE_URL` points to persistent Postgres in production.
- `UNIAPI_API_KEY` set and valid.
- `ZAI_API_KEY` optional fallback.
- `record_context_prompt` set as needed via platform settings.
- Channel provider connectivity healthy (WhatsApp/session active if WhatsApp used).

## Regression Checklist (Run After Changes)

1. Deploy and confirm `/api/v1/ready` == ready.
2. Check `/api/v1/platform/system-health`:
   - `ready=true`
   - `blockers=[]`
3. Send one inbound message.
4. Verify inbound row transitions to `inbound_ai_replied` (or expected controlled state).
5. Verify outbound row exists with:
   - `llm_provider`, `llm_model`, token columns populated
   - `raw_payload.ai_trace` present
6. Verify outbound queue dispatch completes (`sent` or `accepted`).

## Fast Recovery Actions (If Inbound Breaks Again)

1. Check `/api/v1/platform/system-health` first.
2. If schema blocker exists, run schema migration path and redeploy.
3. Validate `et_messages` has all `llm_*` columns.
4. Re-test one inbound message and inspect latest row statuses.

