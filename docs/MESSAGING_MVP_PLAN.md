# Messaging MVP Plan

Status: In Progress (Phase 0 complete, Phase 1 mostly complete)  
Goal: Deliver a simple, reliable, unified messaging architecture for multi-channel inbound/outbound with lightweight CRM intelligence.

## Principles
- Keep one canonical messaging model.
- Keep AI logic in workers, not database triggers.
- Build only what is needed for MVP reliability.
- Reuse the same flow across channels.

## Scope Guardrails
- No event bus for MVP.
- No microservice split for core backend yet.
- No complex orchestration engine.
- One queue, one outbound worker, one inbound worker.
- Add fields/states only when proven necessary.
- No inbound HTTP webhook dependency for message ingestion (Baileys writes inbound directly to Postgres).

## Phase 0 - Alignment
- [x] Freeze canonical flow and table contract from `docs/CHANNEL_API_ARCHITECTURE.md`.
- [x] Confirm only one live messaging model (deprecate conflicting legacy paths).
- [x] Confirm trigger scope: deterministic thread assignment only.
- [x] Publish architecture lock note: `docs/MESSAGING_ARCHITECTURE_LOCK.md`.

Exit Criteria:
- 1-page architecture note signed off.

## Phase 1 - Unified Data Foundation
- [x] Standardize core tables:
- [x] `et_channel_sessions`
- [x] `et_threads`
- [x] `et_messages`
- [x] `et_outbound_queue`
- [x] `et_thread_insights` (minimal: label, next_step, next_followup_at, summary)
- [x] Add essential indexes/constraints:
- [x] Inbound dedupe unique key.
- [x] Queue status index.
- [x] Add one DB trigger to assign/create `thread_id` on inbound insert.
- [x] Disable legacy messaging write paths.
- [x] Draft idempotent SQL migration script: `backend/sql/messaging_m1_unified_schema.sql`.
- [x] Wire SQL migration execution in backend startup (PostgreSQL only).
- [x] Apply and verify migration on local Docker Postgres (`aiworkforme-db-1`).
- [x] Add canonical SQLModel definitions: `backend/src/adapters/db/messaging_models.py`.
- [x] Add minimal unified messaging API scaffold: `backend/routers/messaging.py`.

Exit Criteria:
- Inbound insert auto-gets `thread_id`.
- Duplicate inbound insert is blocked cleanly.
- Messaging writes use canonical tables only.

## Phase 2 - Outbound MVP End-to-End
- [x] API flow: lead selected -> AI generates -> save outbound message -> enqueue.
- [x] Save outbound message + enqueue via `POST /api/v1/messaging/outbound`.
- [ ] Build outbound router worker:
- [x] Poll queue.
- [x] Route by channel (`whatsapp`, `email`, `telegram`).
- [x] Update message and queue status.
- [x] Add retry policy (max 3 attempts with backoff).
- [x] Add outbound dispatch scaffold endpoint: `POST /api/v1/messaging/outbound/dispatch-next` (channel routing + retry state update).

Exit Criteria:
- Outbound send works end-to-end using adapter contract.
- Failures retry then stop with clear error reason.
- No duplicate sends for one queue item.

## Phase 3 - Inbound MVP End-to-End
- [x] Channel API server writes inbound directly into `et_messages`.
- [x] Trigger assigns `thread_id`.
- [ ] Trigger emits `pg_notify` for new inbound message.
- [ ] Inbound worker listens for DB notifications (`LISTEN`) and processes immediately.
- [ ] Keep fallback polling loop (30-60s) to recover missed notifications.
- [x] Build inbound worker:
- [x] Read new inbound messages.
- [x] Label + decide action (`auto_reply`, `follow_up`, `human_takeover`).
- [x] If `auto_reply`, enqueue outbound message.
- [ ] Enforce atomic claim step (`received` -> `inbound_processing`) before runtime call.

Exit Criteria:
- Inbound appears in unified thread timeline.
- Worker decisions are persisted.
- Duplicate inbound delivery does not duplicate stored message.
- Inbound processing still works after worker restart (fallback polling catches missed notify events).

## Phase 4 - CRM Lightweight Intelligence
- [ ] Build thread analyzer job:
- [ ] Summarize thread.
- [ ] Update label/status.
- [ ] Set `next_followup_at`.
- [ ] Persist outputs in `et_thread_insights`.
- [ ] Expose simple read API for CRM view.

Exit Criteria:
- CRM can read full thread + latest insight without parsing raw payload.

## Phase 5 - Security and Stabilization
- [ ] Enforce tenant isolation on all messaging endpoints and workers.
- [ ] Add minimal audit logging:
- [ ] Access denied.
- [ ] Send failure.
- [ ] Worker processing error.
- [ ] Add integration tests:
- [ ] Outbound happy path.
- [ ] Inbound happy path.
- [ ] Inbound dedupe.
- [ ] Tenant isolation.

Exit Criteria:
- Tests pass.
- Messaging stack is pilot-ready.

## Phase 6 - Pilot Rollout
- [ ] Roll out with WhatsApp first.
- [ ] Observe and fix reliability issues.
- [ ] Enable email and telegram using the same adapter contract.

Exit Criteria:
- Stable pilot metrics: send success rate, duplicate suppression, retry behavior.

## Execution Rhythm (Multi-Session)
- Session 1: Phase 0 + Phase 1 design/migration prep.
- Session 2: Phase 1 implementation and verification.
- Session 3: Phase 2 outbound implementation.
- Session 4: Phase 3 inbound implementation.
- Session 5: Phase 4 CRM insights.
- Session 6: Phase 5 hardening/tests.
- Session 7: Phase 6 pilot cutover.
