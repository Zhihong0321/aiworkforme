# Build Phase Milestone Plan (AI Agent Execution + Check Gates)

## 0) Purpose
This is the build-phase control plan for evolving the Eternalgy prototype into the Masterplan MVP.
No build implementation is executed by this plan; it defines sequencing, hard gates, and verification artifacts for AI agents.

## 1) Baseline Snapshot (Input)
- Prototype source: `/Users/ganzhihong/Documents/aiworkfor.me/Eternalgy-MCP-RAG`
- Prototype commit: `cb98683`
- Product source-of-truth: `/Users/ganzhihong/Documents/aiworkfor.me/MASTERPLAN.MD`

## 2) Current Prototype Capability (What Exists)
- FastAPI backend with agent chat endpoint and MCP tool-calling loop.
- MCP server registry/start-stop/tool-call APIs.
- Basic knowledge file upload + retrieval MCP.
- Vue/Vite playground/admin UI with routes for dashboard, agents, MCPs, chat/tester.

## 3) Current Prototype Gaps vs Masterplan (Must Be Closed)
- No workspace/lead lifecycle domain (`LeadStage`, `LeadTag`, takeover/suppression states).
- No immutable safety-floor policy engine (quiet hours, outbound cap, stop rules, opt-out permanence).
- No CRM loops (review loop, due dispatcher, state loop).
- No cost-tier governance (`GREEN/YELLOW/RED`) and no policy-locked routing.
- No WhatsApp webhook/runtime pipeline.
- No analytics for north-star and pilot KPI gates.
- No multi-tenant isolation guarantees.
- No vector embedding pipeline (prototype retrieval is lexical scoring only).

## 4) Milestone Sequencing

### M0. Prototype Hardening Baseline (Readiness Gate)
Objective: Freeze prototype behavior and create migration-safe baseline.

Build tasks:
- Produce architecture inventory for current backend/frontend.
- Define keep/refactor/replace decisions per module.
- Add a compatibility contract doc for model provider abstraction (UniAPI + Gemini 3 Flash Preview).

Exit gate:
- `docs/baseline-inventory.md` exists and reviewed.
- `docs/provider-contract.md` exists with request/response schema and error model.
- Known risks list is explicit (tenant leakage, policy absence, test drift).

Evidence artifacts:
- `docs/baseline-inventory.md`
- `docs/provider-contract.md`
- `docs/risk-register.md`

### M1. Domain Foundation + Schema (Masterplan M1)
Objective: Introduce Masterplan core domain without breaking chat runtime.

Build tasks:
- Add `Workspace`, `Lead`, `ConversationThread`, `PolicyDecision`, `OutreachAttestation`, `StrategyVersion` core schema.
- Add enums: `LeadStage`, `LeadTag`, `BudgetTier`, `FollowUpPreset`.
- Add migration path from prototype `Agent` model to workspace-scoped strategy/agent config.

Exit gate:
- DB migrations apply cleanly forward/backward in dev.
- API schema includes required foundational endpoints from Masterplan section 10.
- Existing chat smoke path still works in compatibility mode.

Evidence artifacts:
- `docs/migrations/m1-foundation.md`
- Migration test log + rollback log
- OpenAPI diff report

### M2. Immutable Policy Engine (Safety Floor)
Objective: Enforce non-bypassable send policy before autonomous dispatch.

Build tasks:
- Implement pre-send policy evaluator:
  - 1 outbound / contact / rolling 24h
  - quiet hours (21:00-09:00 contact local)
  - Sunday hold default
  - suppress after 5 unanswered outbound in 14 days
  - hard opt-out suppression
- Implement policy reason codes + `rule_trace` persistence.
- Block low confidence/risky sends to `STRATEGY_REVIEW_REQUIRED`.

Exit gate:
- All policy tests in Masterplan 12.1 pass.
- Zero code path can send outbound without policy decision record.
- `/v1/workspaces/{id}/policy/decisions` returns reproducible traces.

Evidence artifacts:
- `reports/m2-policy-test-report.json`
- `reports/m2-policy-path-coverage.txt`

### M3. Conversation Agent Runtime
Objective: Convert prototype chat into policy-aware, intent-first conversation execution.

Build tasks:
- Add provider abstraction for UniAPI-backed Gemini routing.
- Add context builder: strategy + memory + retrieval + policy context.
- Add post-generation risk checks and block/retry windows.
- Add takeover handling: `TAKE_OVER` blocks autonomous send/reply.

Exit gate:
- Inbound path and outbound-due path both execute through unified runtime flow.
- Risk-fail never auto-sends.
- Chat/runtime logs emit deterministic decision traces.

Evidence artifacts:
- `reports/m3-runtime-sequence-tests.json`
- `reports/m3-risk-block-tests.json`

### M4. CRM Agent Loops
Objective: Implement scheduling/progression engine around conversations.

Build tasks:
- Hourly review loop (`last_followup_review_at <= now - 24h`).
- Due dispatcher (`next_followup_at <= now`).
- Post-turn state loop for stage/tag progression and memory updates.
- Preset aggressiveness + advanced interval overrides.

Exit gate:
- Loop jobs are idempotent and retry-safe.
- Stage/tag transitions audited.
- `STRATEGY_REVIEW_REQUIRED` routing is automatic on underperformance.

Evidence artifacts:
- `reports/m4-loop-idempotency.json`
- `reports/m4-stage-tag-transition-tests.json`

### M5. RAG, Memory, Cost Governance
Objective: Upgrade from lexical retrieval to budgeted, auditable RAG+memory.

Build tasks:
- Add embedding ingestion + pgvector retrieval.
- Add strategy-linked source priority and context dedup/token packer.
- Add memory layers: short-turn window, rolling summary, long-term facts.
- Add budget tier runtime policies (`GREEN/YELLOW/RED`) including compact red-path behavior.

Exit gate:
- Retrieval quality tests + token-budget tests pass.
- Red-tier still satisfies minimum inbound quality floor.
- Source trace included for retrieval-backed responses.

Evidence artifacts:
- `reports/m5-rag-eval.json`
- `reports/m5-budget-tier-routing.json`

### M6. Core 5 Operator Pages (Masterplan UI Contracts)
Objective: Replace playground/admin with contract-driven MVP pages.

Build tasks:
- Build pages: `Inbox`, `Leads`, `Strategy`, `Knowledge`, `Analytics`.
- Implement component contract template for each component:
  - intent, primary action, inputs, outputs, states, policy hooks, telemetry, acceptance tests.
- Implement `Draft -> Simulate -> Activate` strategy workflow.

Exit gate:
- All page/component contract tests in Masterplan 12.3 pass.
- Blocked send UX always shows reason + next safe action.
- Bulk actions and state audit are traceable.

Evidence artifacts:
- `reports/m6-component-contract-tests.json`
- `reports/m6-ui-smoke-desktop-mobile.md`

### M7. Analytics + KPI Reconciliation
Objective: Make scale decisions measurable against north-star and guardrails.

Build tasks:
- Implement analytics summary endpoint and event aggregation.
- Build scorecards: outcomes/100 leads, split outcomes, policy health, cost efficiency, strategy cohort deltas.
- Reconcile analytics against raw event logs.

Exit gate:
- Analytics reconciliation variance within agreed tolerance.
- Dashboard supports pilot KPI checks directly.

Evidence artifacts:
- `reports/m7-analytics-reconciliation.json`
- `reports/m7-kpi-scorecard-snapshots.md`

### M8. Reliability + Multi-Tenant Hardening
Objective: Enforce production safety under retries/failures/isolation risks.

Build tasks:
- Webhook idempotency keys and dedupe.
- Queue retry/backoff with poison handling.
- MCP timeout/fail-fast/fallback path.
- Cross-workspace data isolation tests.

Exit gate:
- Reliability + isolation tests in Masterplan 12.4 pass.
- No cross-workspace read/write leakage.

Evidence artifacts:
- `reports/m8-reliability-suite.json`
- `reports/m8-tenant-isolation-suite.json`

### M9. Pilot Gate + Launch Readiness
Objective: Validate Masterplan pilot criteria before GA progression.

Build tasks:
- Run controlled pilot workspaces.
- Measure against gate metrics:
  - +15% qualified outcomes / 100 leads
  - <=2.0% negative-signal rate
  - <=20% AI cost share of revenue
  - p95 inbound response <8s
  - zero hard-policy violations

Exit gate:
- All pilot criteria met for agreed observation window.
- Formal go/no-go record signed.

Evidence artifacts:
- `reports/m9-pilot-gate-report.md`
- `reports/m9-go-no-go.md`

## 5) AI Agent Operating Rules During Build
- Never bypass policy engine for convenience.
- Each milestone must be merged only if its exit gate evidence exists.
- If a milestone cannot satisfy a hard gate, mark `BLOCKED` with root cause and mitigation proposal.
- Keep compatibility adapters temporary; remove by end of M6 unless explicitly approved.

## 6) Milestone Status Template (To Reuse Per Milestone)
Use this template in progress logs:

```md
Milestone: Mx
Status: NOT_STARTED | IN_PROGRESS | BLOCKED | PASSED
Scope completed:
Gate checks:
- [ ] Gate 1
- [ ] Gate 2
Evidence:
Risks/notes:
Decision:
```

## 7) Definition of “Ready to Build”
Build execution starts only when:
- M0 artifacts are present and accepted.
- Provider contract for UniAPI + Gemini 3 Flash Preview is locked.
- Acceptance-test harness for M1/M2 is prepared.
