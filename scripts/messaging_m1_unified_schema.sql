-- Messaging M1 Unified Schema (idempotent)
-- Date: 2026-02-18
-- Scope: Canonical messaging tables + deterministic inbound thread assignment trigger.

BEGIN;

CREATE TABLE IF NOT EXISTS et_channel_sessions (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES et_tenants(id) ON DELETE CASCADE,
    channel_type VARCHAR(32) NOT NULL,
    session_identifier VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, channel_type, session_identifier)
);

CREATE INDEX IF NOT EXISTS idx_channel_sessions_tenant ON et_channel_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_channel_sessions_status ON et_channel_sessions(status);

CREATE TABLE IF NOT EXISTS et_threads (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES et_tenants(id) ON DELETE CASCADE,
    lead_id INTEGER NOT NULL REFERENCES et_leads(id) ON DELETE CASCADE,
    channel VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_threads_tenant ON et_threads(tenant_id);
CREATE INDEX IF NOT EXISTS idx_threads_lead ON et_threads(lead_id);
CREATE INDEX IF NOT EXISTS idx_threads_channel ON et_threads(channel);
CREATE INDEX IF NOT EXISTS idx_threads_active ON et_threads(lead_id, channel, status);

CREATE TABLE IF NOT EXISTS et_messages (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES et_tenants(id) ON DELETE CASCADE,
    lead_id INTEGER NOT NULL REFERENCES et_leads(id) ON DELETE CASCADE,
    thread_id BIGINT REFERENCES et_threads(id) ON DELETE SET NULL,
    channel_session_id BIGINT REFERENCES et_channel_sessions(id) ON DELETE SET NULL,
    channel VARCHAR(32) NOT NULL,
    external_message_id VARCHAR(255) NOT NULL,
    direction VARCHAR(16) NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    message_type VARCHAR(32) NOT NULL DEFAULT 'text',
    text_content TEXT,
    media_url TEXT,
    llm_provider VARCHAR(32),
    llm_model VARCHAR(128),
    llm_prompt_tokens INTEGER,
    llm_completion_tokens INTEGER,
    llm_total_tokens INTEGER,
    llm_estimated_cost_usd NUMERIC(12,6),
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    delivery_status VARCHAR(32) NOT NULL DEFAULT 'received',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, channel, external_message_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_tenant ON et_messages(tenant_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON et_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_lead ON et_messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_messages_direction ON et_messages(direction);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON et_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_llm_provider ON et_messages(llm_provider);
CREATE INDEX IF NOT EXISTS idx_messages_llm_model ON et_messages(llm_model);
CREATE INDEX IF NOT EXISTS idx_messages_llm_total_tokens ON et_messages(llm_total_tokens);
CREATE INDEX IF NOT EXISTS idx_messages_tenant_created ON et_messages(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_tenant_provider_created ON et_messages(tenant_id, llm_provider, created_at);

ALTER TABLE et_messages ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(32);
ALTER TABLE et_messages ADD COLUMN IF NOT EXISTS llm_model VARCHAR(128);
ALTER TABLE et_messages ADD COLUMN IF NOT EXISTS llm_prompt_tokens INTEGER;
ALTER TABLE et_messages ADD COLUMN IF NOT EXISTS llm_completion_tokens INTEGER;
ALTER TABLE et_messages ADD COLUMN IF NOT EXISTS llm_total_tokens INTEGER;
ALTER TABLE et_messages ADD COLUMN IF NOT EXISTS llm_estimated_cost_usd NUMERIC(12,6);

UPDATE et_messages
SET
    llm_provider = COALESCE(llm_provider, NULLIF(raw_payload->'ai_trace'->>'provider', '')),
    llm_model = COALESCE(llm_model, NULLIF(raw_payload->'ai_trace'->>'model', '')),
    llm_prompt_tokens = COALESCE(
        llm_prompt_tokens,
        CASE
            WHEN (raw_payload->'ai_trace'->'usage'->>'prompt_tokens') ~ '^[0-9]+$'
            THEN (raw_payload->'ai_trace'->'usage'->>'prompt_tokens')::INTEGER
            ELSE NULL
        END
    ),
    llm_completion_tokens = COALESCE(
        llm_completion_tokens,
        CASE
            WHEN (raw_payload->'ai_trace'->'usage'->>'completion_tokens') ~ '^[0-9]+$'
            THEN (raw_payload->'ai_trace'->'usage'->>'completion_tokens')::INTEGER
            ELSE NULL
        END
    ),
    llm_total_tokens = COALESCE(
        llm_total_tokens,
        CASE
            WHEN (raw_payload->'ai_trace'->'usage'->>'total_tokens') ~ '^[0-9]+$'
            THEN (raw_payload->'ai_trace'->'usage'->>'total_tokens')::INTEGER
            ELSE NULL
        END
    ),
    llm_estimated_cost_usd = COALESCE(
        llm_estimated_cost_usd,
        CASE
            WHEN (raw_payload->'ai_trace'->'usage'->>'estimated_cost_usd') ~ '^[0-9]+(\.[0-9]+)?$'
            THEN (raw_payload->'ai_trace'->'usage'->>'estimated_cost_usd')::NUMERIC(12,6)
            ELSE NULL
        END
    )
WHERE direction = 'outbound';

CREATE TABLE IF NOT EXISTS et_outbound_queue (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES et_tenants(id) ON DELETE CASCADE,
    message_id BIGINT NOT NULL REFERENCES et_messages(id) ON DELETE CASCADE,
    channel VARCHAR(32) NOT NULL,
    channel_session_id BIGINT REFERENCES et_channel_sessions(id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (message_id)
);

CREATE INDEX IF NOT EXISTS idx_outbound_queue_status ON et_outbound_queue(status, next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_outbound_queue_tenant ON et_outbound_queue(tenant_id);

CREATE TABLE IF NOT EXISTS et_thread_insights (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES et_tenants(id) ON DELETE CASCADE,
    thread_id BIGINT NOT NULL REFERENCES et_threads(id) ON DELETE CASCADE,
    lead_id INTEGER NOT NULL REFERENCES et_leads(id) ON DELETE CASCADE,
    label VARCHAR(64),
    next_step VARCHAR(64),
    next_followup_at TIMESTAMP,
    summary TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (thread_id)
);

CREATE INDEX IF NOT EXISTS idx_thread_insights_tenant ON et_thread_insights(tenant_id);
CREATE INDEX IF NOT EXISTS idx_thread_insights_followup ON et_thread_insights(next_followup_at);

CREATE OR REPLACE FUNCTION et_assign_inbound_thread()
RETURNS TRIGGER AS $$
DECLARE
    v_thread_id BIGINT;
BEGIN
    IF NEW.direction <> 'inbound' THEN
        RETURN NEW;
    END IF;

    IF NEW.thread_id IS NOT NULL THEN
        RETURN NEW;
    END IF;

    SELECT id INTO v_thread_id
    FROM et_threads
    WHERE tenant_id = NEW.tenant_id
      AND lead_id = NEW.lead_id
      AND channel = NEW.channel
      AND status = 'active'
    ORDER BY id ASC
    LIMIT 1;

    IF v_thread_id IS NULL THEN
        INSERT INTO et_threads (tenant_id, lead_id, channel, status)
        VALUES (NEW.tenant_id, NEW.lead_id, NEW.channel, 'active')
        RETURNING id INTO v_thread_id;
    END IF;

    NEW.thread_id := v_thread_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_assign_inbound_thread ON et_messages;

CREATE TRIGGER tr_assign_inbound_thread
BEFORE INSERT ON et_messages
FOR EACH ROW
EXECUTE FUNCTION et_assign_inbound_thread();

COMMIT;
