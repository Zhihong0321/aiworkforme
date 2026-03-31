# Calendar Production Implementation Plan

## Objective

Build Calendar into a production scheduling system that allows an AI agent to:

- detect scheduling intent
- check a tenant user's real availability
- validate meeting type and region
- create confirmed appointments when all details are valid
- create pending appointments when the lead is willing to meet but details are incomplete or invalid
- never claim a booking succeeded unless Calendar returned success

Calendar is the tenant's scheduling system of record. The AI should use it through structured tool calls, not free-text guessing.

## Recommended Architecture

Use a hybrid design:

- MCP for execution and persistence
- prompt rules / conversation skill text for behavioral guidance

### Why MCP is the primary execution layer

Calendar needs:

- strict tenant scoping
- structured arguments
- deterministic validation
- auditability
- overlap prevention
- idempotency

These are system-of-record concerns. They belong in services and MCP tools, not only in prompt instructions.

### Why prompt rules still matter

The AI still needs behavioral guidance:

- when to call Calendar
- when not to promise a booking
- when to ask for missing details
- when to create a pending appointment instead of forcing a slot

## Product Contract

### Agent toggle behavior

If `calendar_enabled = false`:

- AI may discuss scheduling in conversation
- AI may collect preference details from the lead
- AI must not confirm a booking
- AI must not write to calendar events

If `calendar_enabled = true`:

- AI must use Calendar before confirming a meeting
- AI may check availability
- AI may confirm a booking
- AI may create a pending appointment

### Booking outcomes

Calendar actions must resolve to one of these outcomes:

- `confirmed`: appointment written successfully with exact slot and region
- `pending`: lead wants to meet, but details are incomplete or cannot be validated yet
- `rejected`: request is invalid and should not create an event
- `error`: internal failure; AI must not pretend success

### Pending appointment rule

Create a pending appointment when the lead is willing to meet but one or more of these is true:

- exact date or time is missing
- requested slot is unavailable
- requested region is not allowed
- meeting type is unclear
- tenant setup is incomplete but the lead is clearly interested

Pending appointments are intentionally human-follow-up tasks. They should notify the tenant user that the lead is qualified for direct scheduling assistance.

## Data Model Changes

## Agent

Extend the agent model with:

- `calendar_enabled: bool = false`
- `calendar_owner_user_id: Optional[int]`
- `calendar_require_region_validation: bool = true`
- `calendar_require_meeting_type_validation: bool = true`

Optional future fields:

- `calendar_auto_create_pending: bool = true`
- `calendar_allowed_meeting_type_names: JSON list`
- `calendar_allowed_regions: JSON list`

### Purpose

- `calendar_enabled` controls whether Calendar tools are exposed to this agent
- `calendar_owner_user_id` identifies the tenant user whose calendar is checked and booked

## Tenant / Calendar Config

Extend `CalendarConfig` or add supporting tables so tenant scheduling rules are explicit:

- `tenant_id`
- `user_id`
- `timezone`
- `working_hours`
- `buffer_minutes`
- `advance_notice_minutes`
- `meeting_types`
- `available_regions`
- `default_meeting_duration_minutes`
- `calendar_enabled`

Recommended shape:

- `meeting_types`: list of objects
- `available_regions`: list of strings
- `working_hours`: structured object keyed by weekday

Example `meeting_types` entry:

```json
{
  "name": "Discovery Call",
  "duration_minutes": 30,
  "description": "Initial sales qualification call",
  "allowed_regions": ["Online", "Kuala Lumpur"],
  "requires_region": true
}
```

## Calendar Event

Extend `CalendarEvent` with:

- `agent_id: Optional[int]`
- `source: str`
- `needs_human_followup: bool`
- `pending_reason: Optional[str]`
- `customer_notes: Optional[str]`
- `requested_start_time: Optional[datetime]`
- `requested_end_time: Optional[datetime]`
- `resolution_notes: Optional[str]`

Use `status` values:

- `confirmed`
- `pending`
- `cancelled`
- `completed`

Use `source` values:

- `ai_agent`
- `tenant_user`
- `manual`
- `migration`

## Audit Table

Add a dedicated audit table, for example `et_calendar_action_logs`, with:

- `id`
- `tenant_id`
- `agent_id`
- `user_id`
- `lead_id`
- `event_id`
- `tool_name`
- `action`
- `request_payload`
- `result_payload`
- `result_status`
- `error_message`
- `created_at`

This is required for production debugging.

## Database Constraints And Indexes

Add indexes:

- `(tenant_id, user_id, start_time)`
- `(tenant_id, user_id, status)`
- `(tenant_id, lead_id)`
- `(tenant_id, needs_human_followup, status)`

Add server-side overlap protection for confirmed events:

- prevent overlapping `confirmed` events for the same `tenant_id + user_id`
- pending events should not block availability

## Service Layer

Create a dedicated calendar service module that becomes the single business-logic path for scheduling.

Suggested file:

- `backend/src/app/runtime/calendar_service.py`

### Responsibilities

- resolve calendar owner
- validate tenant scoping
- validate meeting type
- validate region
- normalize input timezone
- compute availability
- prevent overlaps
- create confirmed appointment
- create pending appointment
- reschedule appointment
- cancel appointment
- write audit logs
- return structured result objects

### Recommended service methods

- `get_calendar_owner_for_agent(...)`
- `get_calendar_capabilities(...)`
- `get_user_availability(...)`
- `book_appointment(...)`
- `create_pending_appointment(...)`
- `reschedule_appointment(...)`
- `cancel_appointment(...)`

### Important rule

The service, not the model, must decide whether a request becomes `confirmed`, `pending`, `rejected`, or `error`.

## MCP Design

Calendar should remain an MCP for execution.

Suggested MCP tools:

- `get_calendar_capabilities`
- `get_user_availability`
- `book_appointment`
- `create_pending_appointment`
- `reschedule_appointment`
- `cancel_appointment`

### MCP request identity

The AI must never be responsible for internal identity fields. The runtime should inject:

- `tenant_id`
- `calendar_owner_user_id`
- `agent_id`

The model may provide:

- `lead_id`
- `meeting_type_name`
- `region`
- `title`
- `description`
- `requested_start_time`
- `requested_end_time`
- customer intent notes

### MCP response contract

Each write tool should return structured JSON:

```json
{
  "status": "confirmed",
  "event_id": 123,
  "message_for_ai": "Booked for 2026-04-02 10:00 Asia/Shanghai.",
  "reason": null,
  "suggested_next_action": "confirm_to_customer"
}
```

Examples of `status`:

- `confirmed`
- `pending`
- `rejected`
- `error`

Examples of `suggested_next_action`:

- `confirm_to_customer`
- `ask_for_missing_details`
- `handoff_to_tenant_user`
- `offer_alternative_slots`

## Agent Runtime Integration

Calendar behavior must be unified across:

- `/api/v1/chat`
- autonomous inbound runtime
- any playground or internal testing runtime that can book appointments

## Shared scheduling detection

Extract scheduling detection into a shared helper so all runtimes use the same logic.

Suggested file:

- `backend/src/app/runtime/calendar_intent.py`

Suggested helpers:

- `is_scheduling_request(text)`
- `is_calendar_tool(tool_name)`
- `sanitize_calendar_tool_schema(tool_def)`
- `inject_calendar_tool_args(tool_name, tool_args, runtime_identity)`

## Runtime rules

When:

- `calendar_enabled = true`
- the request is a scheduling request
- a calendar MCP is linked and available

Then:

- runtime must force tool usage on the first turn
- runtime must inject calendar behavior rules into the system prompt
- runtime must inject owner identity into MCP args
- runtime must not allow final confirmation text before a successful tool result

When:

- `calendar_enabled = false`

Then:

- do not expose calendar tools
- AI may collect preferences only

## Prompt Rules

Add a reusable prompt block for calendar-aware agents:

- for availability, scheduling, booking, rescheduling, or appointment requests, use Calendar before answering
- never say an appointment is booked unless Calendar returned `confirmed`
- if the lead wants to meet but the details cannot be finalized, create a pending appointment
- if details are missing, ask a concise follow-up question
- never invent internal IDs

This prompt guidance should complement MCP, not replace it.

## API And UI Changes

## Agent Settings UI

Add to agent settings:

- `Calendar Enabled` toggle
- `Calendar Owner` selector
- optionally allowed meeting types
- optionally allowed regions

Suggested backend fields should be surfaced through:

- `GET /agents/{id}`
- `PUT /agents/{id}`
- `POST /agents/`

## Calendar Settings UI

Expand tenant calendar management to include:

- timezone
- working hours
- meeting types
- available regions
- buffer and notice rules
- default calendar owner

## Pending Appointment Inbox

Add a list in the Calendar or Agent workspace showing:

- lead
- agent
- requested time
- requested region
- meeting type
- pending reason
- owner user
- created time
- action to confirm, cancel, or convert

## Rollout Phases

## Phase 1: Foundation

- add schema fields for agent calendar toggle and owner
- extend calendar event status model
- add audit table
- create calendar service

Acceptance:

- tenant user can configure a calendar owner
- agent can be calendar-enabled
- pending and confirmed event statuses exist

## Phase 2: MCP Upgrade

- upgrade Calendar MCP to structured tool responses
- implement `create_pending_appointment`
- move write logic into service layer

Acceptance:

- MCP can create confirmed and pending appointments
- MCP logs audit records
- overlap checks work

## Phase 3: Runtime Unification

- extract shared calendar intent and tool helpers
- apply same enforcement to chat and inbound runtime
- inject owner identity safely

Acceptance:

- chat and inbound runtime behave the same for scheduling
- AI never confirms a booking without tool success

## Phase 4: UI And Operations

- add agent toggle and owner selector
- add pending appointment inbox
- add debug visibility for calendar actions

Acceptance:

- operators can turn Calendar on and off per agent
- operators can see pending appointments and follow up

## Phase 5: Production Hardening

- add idempotency keys
- add retry-safe writes
- add metrics and alerting
- add timezone regression tests

Acceptance:

- retries do not create duplicate bookings
- failures are visible in logs and metrics
- tenant boundaries are enforced

## Testing Strategy

## Unit tests

- meeting type validation
- region validation
- overlap logic
- pending appointment decision logic
- owner resolution logic
- timezone normalization

## Integration tests

- agent with Calendar OFF cannot book
- agent with Calendar ON can confirm valid slot
- unresolved slot creates pending appointment
- out-of-region request creates pending appointment
- missing meeting type creates pending appointment or follow-up
- duplicate MCP retries do not double-book

## Runtime tests

- `/api/v1/chat` scheduling request forces tool usage
- inbound runtime scheduling request forces tool usage
- runtime injects owner identity and strips internal IDs from model schema
- AI reply text matches MCP result status

## Debug And Observability

Add:

- audit logs for all Calendar MCP calls
- recent calendar action endpoint
- failed calendar action endpoint
- pending appointment count metrics
- confirmed booking count metrics

Suggested debug endpoint:

- `GET /api/v1/debug/calendar?tenant_id=...`

Suggested response:

- recent tool calls
- recent confirmed events
- recent pending events
- recent failures

## Recommended Defaults

- `calendar_enabled = false` for new agents unless product decides otherwise
- `calendar_auto_create_pending = true`
- default meeting duration = 30 minutes
- timezone must come from tenant calendar config, not model text
- pending events do not block availability

## Key Open Decisions

- Should new agents auto-link Calendar MCP when `calendar_enabled` is switched on?
- Should there be a tenant-level default calendar owner fallback?
- Should a missing owner block all scheduling, or allow pending appointments only?
- Should meeting types and regions be tenant-wide only, or also overrideable per agent?

## Recommended Answers To Open Decisions

- Yes, auto-link Calendar MCP when `calendar_enabled` becomes true if the tenant has a Calendar server registered.
- Yes, support a tenant default owner as a fallback.
- If owner is missing, allow `pending` only and block `confirmed`.
- Keep meeting types and regions tenant-wide first, then add per-agent restriction later if needed.

## Delivery Summary

Build Calendar as:

- a tenant scheduling core with explicit rules
- an MCP execution layer for deterministic actions
- a shared runtime integration so all agent paths behave consistently
- a per-agent toggle that exposes or hides Calendar capability
- a pending-appointment workflow for high-intent leads whose details are not final yet

This approach matches the product goal: the AI can schedule responsibly, and when it cannot finalize details, it still captures business intent for the tenant to close manually.
