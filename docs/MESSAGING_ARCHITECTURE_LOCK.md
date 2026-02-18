# Messaging Architecture Lock (MVP)

Date: 2026-02-18  
Status: Locked for implementation (Phase 0 complete)

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
- Channel API server writes inbound directly into `et_messages`.
- Database trigger deterministically assigns `thread_id`.
- Inbound worker performs AI labeling/decision (auto-reply, follow-up, human takeover).

3. CRM
- CRM worker reads unified thread history from `et_messages` + `et_threads`.
- CRM stores summary/label/next step/follow-up in `et_thread_insights`.

## Trigger Scope (Strict)
Database trigger responsibilities:
- Assign/create thread for inbound message.
- No AI logic.
- No external calls.

All AI/CRM decisions run in workers.

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
