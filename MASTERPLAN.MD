# Master Build Foundation v2: AI Customer Approach App (Intent-First, Cost-First with Safety Floor)

## Summary
This document is the single source of truth for product intent, autonomous logic, milestone gates, and page/component contracts for the MVP.
The product intent is to help a single SMB operator run persistent WhatsApp outreach that converts leads to `appointment` or `purchase` outcomes with minimal manual effort, while protecting trust through immutable anti-spam rules and protecting margin through hard budget tiers.
This foundation is decision-complete for implementation planning and is explicitly scoped to the core 5 pages: `Inbox`, `Leads`, `Strategy`, `Knowledge`, `Analytics`.

## 1) App Intent Statement (North-Star Doctrine)
1. Mission: Automate consistent lead approach and follow-up at scale so SMBs win more qualified outcomes without increasing headcount.
2. Outcome promise: Improve `qualified outcomes per 100 leads` with safe, polite, time-aware outreach.
3. Product posture: `Cost first`, but never below immutable safety/trust controls.
4. Autonomy posture: No manual approval loop for normal operations; risky/low-confidence sends are blocked and routed to `Strategy Review Required`.
5. Scope posture: WhatsApp-first via SaaS API provider, multi-tenant SaaS, single operator workflow.
6. Non-goals for MVP: Omnichannel orchestration, team role hierarchy, built-in payment rails, custom WhatsApp infra.

## 2) User Expected Value, Function, Result

### 2.1 Expected user value
1. Persistent follow-up execution with minimal operator fatigue.
2. Faster response consistency on inbound messages.
3. Higher conversion confidence through stage/tag visibility.
4. Better margin control via token-cost governance.
5. Clear intervention queue for hard leads (`Strategy Review Required`).

### 2.2 Functional result model
1. Input: User provides contacts, strategy profile, knowledge, product info, and aggressiveness settings.
2. System action: Conversation Agent and CRM Agent execute ongoing outreach/review/scheduling loops.
3. Output: Leads progress through canonical lifecycle and terminate in appointment, purchase, suppression, or takeover.
4. Business result: Pilot target `+15% qualified outcomes per 100 leads` with `<=2.0% negative-signal rate` and `<=20% AI cost share of revenue`.

## 3) Main Pillar A: Conversation Agent (Autonomous Messaging Core)

### 3.1 Pillar intent
1. Generate context-aware, goal-directed messages and replies that move leads toward appointment/purchase outcomes.

### 3.2 Deterministic runtime flow
1. Receive event (`inbound` or `outbound_due`).
2. Resolve workspace, lead, timezone, stage, tags, budget tier.
3. Execute pre-send policy evaluation.
4. Build prompt context from strategy, memory, RAG, product facts.
5. Route task to model tier.
6. Generate candidate message.
7. Execute post-generation policy/risk validation.
8. Send or block.
9. Persist message, decision log, memory update, and analytics event.

### 3.3 Autonomy contract
1. Inbound receives fast response path with compact context when budget is constrained.
2. Outbound obeys hard cap, quiet hours, stop/suppression rules.
3. Low confidence or risky content never auto-sends.
4. Blocked leads enter `Strategy Review Required`.
5. `TAKE_OVER` state pauses all autonomous outbound and inbound auto-replies.

## 4) Main Pillar B: CRM Agent (Review, Scheduling, Progress Engine)

### 4.1 Pillar intent
1. Decide next follow-up timing and pipeline movement based on conversation signals and policy constraints.

### 4.2 Scheduled loops
1. Hourly `Review Loop`: reevaluate leads with `last_followup_review_at <= now - 24h`.
2. Continuous `Due Dispatcher`: trigger leads where `next_followup_at <= now`.
3. Post-turn `State Loop`: update stage/tags/memory after each conversation event.

### 4.3 Follow-up aggressiveness model
1. Presets: `Gentle`, `Balanced`, `Aggressive`.
2. Advanced override: workspace-level interval customization.
3. Global hard outbound limits override preset behavior.
4. Explicit customer cue can override cadence timing only when cue is clear and recent.

### 4.4 Lead intelligence outputs
1. Stage transition recommendation.
2. Behavioral tag updates.
3. Next follow-up timestamp.
4. Strategy effectiveness signal.
5. `Strategy Review Required` routing when baseline playbook underperforms.

## 5) Main Pillar C: User Dashboard (Operator Control Plane)

### 5.1 Pillar intent
1. Give the operator precise control and visibility over autonomous behavior, strategy quality, and outcomes.

### 5.2 Dashboard structure
1. Default landing page: `Inbox`.
2. Core pages: `Inbox`, `Leads`, `Strategy`, `Knowledge`, `Analytics`.
3. Alerting mode: in-app alerts only.
4. Strategy rollout mode: `Draft -> Simulate -> Activate`.

## 6) Spam Control Policy (Immutable Safety Floor)

### 6.1 Hard send rules
1. Outbound cap: max `1 outbound per contact per rolling 24h`.
2. Quiet hours: block outbound `9:00 PM to 9:00 AM` in contact-local timezone.
3. Unknown timezone fallback: workspace timezone.
4. Send days: `Mon-Sat` allowed, `Sunday` hold by default.
5. Stop rule: suppress after `5 unanswered outbound` in `14 days`.
6. Explicit cue override: allowed only for direct timing cues from customer.
7. Opt-out/disconnect: immediate permanent suppression unless user manually re-enables with audit reason.

### 6.2 Outreach permission model
1. Workspace attestation required for lawful outreach permission.
2. No strict pre-opt-in gate in MVP.
3. Hard opt-out suppression is mandatory and immutable.

### 6.3 Risk behavior without manual approvals
1. If confidence/risk check fails, do not send.
2. Tag lead `STRATEGY_REVIEW_REQUIRED`.
3. Create in-app alert with block reason.
4. Retry only after strategy update or next safe window.

## 7) Cost, RAG, Memory, and MCP/Skills Architecture

### 7.1 Cost-first runtime governance
1. Budget tiers: `Green <80%`, `Yellow 80-95%`, `Red >95%`.
2. Yellow mode: smaller context, cheaper model routing, tighter tool budget.
3. Red mode: preserve inbound responses on compact path, throttle non-critical outbound.
4. Cost controls cannot disable immutable safety floor.

### 7.2 RAG architecture (pgvector-backed)
1. Chunk ingestion with metadata and embeddings.
2. Strategy-linked source priority over workspace default.
3. Retrieval uses semantic rank plus policy filters.
4. Context packer enforces strict token budgets and de-duplication.
5. Response includes source trace for auditability.

### 7.3 Memory architecture
1. Short-term turn window.
2. Rolling lead summary snapshots.
3. Long-term fact memory embeddings.
4. Policy memory counters for outreach constraints.

### 7.4 Context cache strategy
1. Cache prompt prefixes by workspace + strategy version.
2. Reuse stable system/instruction blocks.
3. Cache retrieval summaries for repeated intents in active windows.

### 7.5 MCP + SKILL runtime (in MVP)
1. Skill/tool allowlist per workspace.
2. Max tool-call count per response.
3. Tool timeout and fail-fast policy.
4. Tool failures degrade gracefully to non-tool reply path.

## 8) Lifecycle, Stages, and Tags (Decision Complete)

### 8.1 Canonical lifecycle stages
1. `NEW`
2. `CONTACTED`
3. `ENGAGED`
4. `QUALIFIED`
5. `OUTCOME_APPOINTMENT`
6. `OUTCOME_PURCHASE`
7. `TAKE_OVER`
8. `CLOSED_LOST`
9. `SUPPRESSED`

### 8.2 Behavioral and risk tags
1. `NO_RESPONSE`
2. `NEUTRAL`
3. `POSITIVE`
4. `RESISTIVE`
5. `DISCONNECT`
6. `STRATEGY_REVIEW_REQUIRED`
7. `INTENT_APPOINTMENT`
8. `INTENT_PURCHASE`

### 8.3 Design rule
1. Stage is lifecycle progress.
2. Tags are behavior/risk/intent overlays.
3. Automation must never replace stage with tags or vice versa.

## 9) Core 5 Pages: Intent Charters and Component Contracts

### 9.1 Contract template (mandatory for every component)
1. `Intent`: why component exists.
2. `Primary action`: operator action to complete.
3. `Inputs`: data/events required.
4. `Outputs`: state changes/events emitted.
5. `States`: loading/empty/ready/error/suppressed variants.
6. `Policy hooks`: required safety/cost checks.
7. `Telemetry`: events and KPI signals.
8. `Acceptance tests`: pass/fail behavior checks.

### 9.2 Inbox page charter
1. Intent: resolve live conversations and exceptions fast and safely.
2. KPI: median time-to-action under 60 seconds.
3. Component `Conversation Timeline`: shows message history with policy badges; outputs reply/send/takeover actions.
4. Component `AI Draft Panel`: generates/editable candidate reply; blocks on risk fail and shows reason.
5. Component `Lead Context Card`: stage/tags/next follow-up/memory summary snapshot.
6. Component `Action Bar`: takeover, suppress, schedule-next, mark-outcome actions with audit logging.
7. Component `Policy Alert Strip`: visible when send blocked, quiet hours active, or budget tier changed.

### 9.3 Leads page charter
1. Intent: control pipeline at list level with bulk-safe operations.
2. KPI: time to identify and act on priority leads.
3. Component `Lead Table`: filter/sort by stage/tags/next due/last touch.
4. Component `Bulk Action Panel`: apply strategy, pause/resume, suppress, takeover.
5. Component `Priority Queue`: auto-ranked due leads and `Strategy Review Required`.
6. Component `Import Wizard`: contact import with attestation acknowledgment and validation results.
7. Component `State Audit Drawer`: show recent state transitions and policy decisions.

### 9.4 Strategy page charter
1. Intent: author and validate conversation playbook before production rollout.
2. KPI: strategy iteration success rate and regression prevention.
3. Component `Strategy Editor`: tone, objectives, objection handling, CTA rules.
4. Component `Aggressiveness Config`: preset selector and advanced interval overrides.
5. Component `Simulation Bench`: run scenario tests against sample leads.
6. Component `Version Manager`: draft, compare diff, activate, rollback.
7. Component `Recovery Playbook Builder`: lead-specific tactics for `Strategy Review Required`.

### 9.5 Knowledge page charter
1. Intent: maintain accurate retrieval context with low token waste.
2. KPI: retrieval relevance and hallucination reduction.
3. Component `Source Library`: upload/manage docs and metadata.
4. Component `Chunk Inspector`: inspect chunk quality and overlap.
5. Component `Priority Mapper`: link sources to strategy profiles and intents.
6. Component `Freshness Monitor`: stale-source alerts and update reminders.
7. Component `Retrieval Debug View`: query/result traces and token footprint.

### 9.6 Analytics page charter
1. Intent: show whether automation is improving outcomes safely and profitably.
2. KPI: decision speed and confidence in scaling actions.
3. Component `North-Star Scorecard`: qualified outcomes per 100 leads.
4. Component `Outcome Split`: appointment vs purchase conversion.
5. Component `Policy Health`: block rate, negative-signal rate, suppression patterns.
6. Component `Cost Efficiency`: token per qualified outcome and budget tier trend.
7. Component `Strategy Cohort Compare`: version-level performance deltas.

## 10) Public APIs, Interfaces, and Type Additions

### 10.1 New/updated APIs
1. `POST /v1/workspaces/{id}/attestation/outreach-permission`
2. `POST /v1/workspaces/{id}/leads/import`
3. `POST /v1/workspaces/{id}/leads/{leadId}/start`
4. `POST /v1/integrations/whatsapp/webhook`
5. `POST /v1/workspaces/{id}/strategy/drafts`
6. `POST /v1/workspaces/{id}/strategy/{draftId}/simulate`
7. `POST /v1/workspaces/{id}/strategy/{draftId}/activate`
8. `POST /v1/workspaces/{id}/leads/{leadId}/takeover`
9. `POST /v1/workspaces/{id}/leads/{leadId}/release`
10. `POST /v1/workspaces/{id}/leads/{leadId}/suppress`
11. `GET /v1/workspaces/{id}/analytics/summary`
12. `GET /v1/workspaces/{id}/policy/decisions`

### 10.2 Core types
1. `LeadStage` enum and `LeadTag` enum.
2. `PolicyDecision` with `allow_send`, `reason_code`, `next_allowed_at`, `rule_trace`.
3. `BudgetTier` enum: `GREEN`, `YELLOW`, `RED`.
4. `StrategyVersion` with `status` (`DRAFT`, `ACTIVE`, `ROLLED_BACK`) and simulation metrics.
5. `FollowUpPreset` and `FollowUpIntervalPolicy`.
6. `OutreachAttestation` record with timestamp and operator identity.
7. `ComponentTelemetryEvent` contract for all UI components.

## 11) Milestones and Stage Gates

### 11.1 Delivery milestones
1. M1 Foundation: tenant model, webhook ingest, policy engine skeleton, core data schema.
2. M2 Autonomy loop: CRM review/dispatcher, stage/tag transitions, stop/suppress logic.
3. M3 Operator pages: Inbox and Leads full contracts implemented.
4. M4 Strategy/Knowledge: simulation pipeline, RAG priority routing, memory compression.
5. M5 Analytics and hardening: KPI dashboards, load/retry/idempotency testing.
6. M6 Pilot launch: internal + 5 pilot workspaces.
7. M7 Controlled GA: release after pilot gate pass.

### 11.2 Pilot gate criteria
1. `+15%` qualified outcomes per 100 leads versus baseline.
2. `<=2.0%` negative-signal rate.
3. `<=20%` AI operating cost share of workspace revenue.
4. p95 inbound response under 8 seconds.
5. Zero hard-policy violations in outbound logs.

## 12) Test Cases and Scenarios (Required)

### 12.1 Policy and autonomy tests
1. Outbound cap enforcement across timezone boundaries.
2. Quiet-hours blocking and next-window scheduling.
3. Explicit cue override acceptance and rejection paths.
4. Stop-rule suppression after unanswered sequence.
5. `DISCONNECT` immediate suppression.
6. `TAKE_OVER` blocks all autonomous sends.

### 12.2 RAG and memory tests
1. Strategy-linked source priority over workspace default.
2. Retrieval result quality under token budget tiers.
3. Context de-duplication behavior.
4. Memory summary correctness after long conversations.
5. Red-tier compact path response quality floor.

### 12.3 Page/component contract tests
1. Inbox send blocked state exposes reason and next action.
2. Leads bulk action audit entries generated correctly.
3. Strategy simulation must pass before activation.
4. Knowledge retrieval debug shows source trace and token use.
5. Analytics values reconcile with event logs within acceptable variance.

### 12.4 Reliability and isolation tests
1. Webhook idempotency under retries.
2. Queue retry/backoff correctness.
3. Multi-tenant isolation and no cross-workspace leaks.
4. Budget tier transitions trigger correct runtime behavior.
5. Tool-call timeout fallback path for MCP/skills.

## 13) Change Control and Governance

### 13.1 Foundation change process
1. Use formal change log only.
2. Each change requires reason, impact score, KPI effect, cost/timeline delta, owner.
3. Changes touching safety floor require explicit approval and migration note.
4. Changes touching stage/tag semantics require analytics compatibility note.
5. No silent scope edits in implementation tickets.

### 13.2 AI builder decision rules
1. Follow this foundation before local optimization.
2. If unclear, choose lower-cost option that does not weaken safety floor.
3. Never bypass immutable policy checks for feature convenience.
4. Emit telemetry for every autonomous decision path.
5. Prefer reversible strategies and versioned rollout.

## 14) Explicit Assumptions and Defaults

1. WhatsApp transport and policy compliance at API layer are managed by third-party SaaS.
2. Single operator is the day-to-day persona for MVP.
3. Multi-tenant architecture is mandatory from day one.
4. In-app alerts are sufficient for MVP operations.
5. Data retention is 12 months active plus archive.
6. Security baseline is standard DB encryption; stronger PII controls are planned post-MVP.
7. Outbound permission is based on workspace attestation with mandatory opt-out suppression.
8. Primary target remains general SMB; strategy and taxonomy must remain template-driven, not industry-hardcoded.
