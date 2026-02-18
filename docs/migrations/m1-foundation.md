# Migration M1: Domain Foundation

## Objective
Introduce the Masterplan core domain entities to the database schema to support multi-tenant lead management and outreach policy enforcement.

## New Entities

### Core Enums
- `LeadStage`: NEW, CONTACTED, ENGAGED, QUALIFIED, OUTCOME_APPOINTMENT, OUTCOME_PURCHASE, TAKE_OVER, CLOSED_LOST, SUPPRESSED.
- `LeadTag`: NO_RESPONSE, NEUTRAL, POSITIVE, RESISTIVE, DISCONNECT, STRATEGY_REVIEW_REQUIRED, INTENT_APPOINTMENT, INTENT_PURCHASE.
- `BudgetTier`: GREEN, YELLOW, RED.
- `FollowUpPreset`: GENTLE, BALANCED, AGGRESSIVE.
- `StrategyStatus`: DRAFT, ACTIVE, ROLLED_BACK.

### Tables
1.  **Workspace** (`workspace`)
    - `id` (PK)
    - `name` (String)
    - `timezone` (String, default UTC)
    - `budget_tier` (BudgetTier, default GREEN)
    - `created_at` (DateTime)

2.  **StrategyVersion** (`strategy_version`)
    - `id` (PK)
    - `workspace_id` (FK -> workspace.id)
    - `version_number` (Int)
    - `status` (StrategyStatus, default DRAFT)
    - `tone` (Text)
    - `objectives` (Text)
    - `objection_handling` (Text)
    - `cta_rules` (Text)
    - `followup_preset` (FollowUpPreset)
    - `interval_overrides` (JSONB)
    - `created_at` (DateTime)
    - `activated_at` (DateTime, Nullable)

3.  **Lead** (`lead`)
    - `id` (PK)
    - `workspace_id` (FK -> workspace.id)
    - `external_id` (String, Index) - e.g. Phone number/WhatsApp ID
    - `name` (String, Nullable)
    - `stage` (LeadStage, default NEW)
    - `tags` (JSONB / Array of LeadTag)
    - `timezone` (String, Nullable)
    - `last_followup_at` (DateTime, Nullable)
    - `next_followup_at` (DateTime, Nullable)
    - `last_followup_review_at` (DateTime, Nullable)
    - `created_at` (DateTime)

4.  **ConversationThread** (`conversation_thread`)
    - `id` (PK)
    - `workspace_id` (FK -> workspace.id)
    - `lead_id` (FK -> lead.id)
    - `status` (String, default "active")
    - `created_at` (DateTime)

5.  **ChatMessage** (`chat_message`)
    - `id` (PK)
    - `thread_id` (FK -> conversation_thread.id)
    - `role` (String) - user, model, system
    - `content` (Text)
    - `tool_calls` (JSONB, Nullable)
    - `created_at` (DateTime)

6.  **PolicyDecision** (`policy_decision`)
    - `id` (PK)
    - `workspace_id` (FK -> workspace.id)
    - `lead_id` (FK -> lead.id)
    - `allow_send` (Bool)
    - `reason_code` (String)
    - `rule_trace` (JSONB)
    - `next_allowed_at` (DateTime, Nullable)
    - `created_at` (DateTime)

7.  **OutreachAttestation** (`outreach_attestation`)
    - `id` (PK)
    - `workspace_id` (FK -> workspace.id)
    - `operator_id` (String)
    - `timestamp` (DateTime)
    - `granted` (Bool, default True)

## Backward Compatibility
- Prototype `Agent` model will eventually map to a specific `StrategyVersion` in a default `Workspace`.
- Prototype `ChatSession` will map to `ConversationThread`.
- Prototype `ChatMessage` (prefixed `zairag_`) will remain for now to ensure existing paths work.

## Migration Steps
1.  Define models in `backend/models.py`.
2.  Use `SQLModel.metadata.create_all(engine)` or an Alembic migration script.
3.  Seed a default Workspace for prototype agents to use.
