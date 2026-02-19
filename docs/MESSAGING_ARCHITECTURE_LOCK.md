# Messaging Architecture Lock (MVP)

Date: 2026-02-18  
Status: Locked for implementation (Phase 0 complete, inbound trigger/event update on 2026-02-19)

## Objective
Establish one canonical, multi-channel messaging workflow that is simple, reliable, and CRM-friendly.

## Canonical Data Model
The messaging domain uses these tables only:
- `et_channel_sessions`
- `et_threads`
- `et_messages`
- `et_outbound_queue`
- `et_thread_insights`

Legacy messaging paths are deprecated for new writes:
- `et_conversation_threads`
- `et_chat_messages`

## Workflow Contract
1. Outbound
- App creates outbound record in `et_messages`.
- App enqueues send task in `et_outbound_queue`.
- Outbound router sends by channel (`whatsapp`, `email`, `telegram`) and updates status.

2. Inbound
- Baileys/Channel API server writes inbound directly into `et_messages` (no inbound HTTP webhook dependency).
- Database trigger deterministically assigns `thread_id` and emits DB notification for new inbound rows.
- Inbound worker consumes DB notifications (plus fallback polling) and performs AI labeling/decision (auto-reply, follow-up, human takeover).

3. CRM
- CRM worker reads unified thread history from `et_messages` + `et_threads`.
- CRM stores summary/label/next step/follow-up in `et_thread_insights`.

## Trigger Scope (Strict)
Database trigger responsibilities:
- Assign/create thread for inbound message.
- Emit lightweight DB event (`pg_notify`) for inbound processing wake-up.
- No AI logic.
- No external calls.

All AI/CRM decisions run in workers.

## Inbound Worker Contract (MVP)
- Deployment model: single backend instance for launch.
- Processing model: `LISTEN/NOTIFY` for near-real-time + fallback polling for crash/restart recovery.
- Message claim model: only process rows in `delivery_status='received'`, then atomically transition to `inbound_processing` before AI runtime.
- Existing fields are canonical state markers:
  - `direction='inbound'`
  - `delivery_status` lifecycle (`received` -> `inbound_processing` -> `inbound_ai_replied` / `inbound_human_takeover` / `inbound_error`)
- No new "unreplied" column for MVP unless proven necessary by production evidence.

## Idempotency Contract
- Inbound dedupe key: `(tenant_id, channel, external_message_id)`.
- Outbound queue guarantees one dispatch lifecycle per queue row.

## Security Contract
- All routes and workers are tenant-scoped.
- Any cross-tenant access attempt is denied and logged.

## Why This Is Lean
- One canonical schema.
- One outbound queue.
- One outbound router worker.
- One inbound decision worker.
- No event bus or extra orchestration layer for MVP.
