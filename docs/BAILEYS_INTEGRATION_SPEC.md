# BAILEYS WHATSAPP API - POSTGRESQL INTEGRATION SPECIFICATION

Version: 1.0
Date: 2026-02-17
Project: AIworkforMe Multi-Channel Sales AI Agent
Target Audience: AI Agent (Baileys Implementation Team)
Document Format: Pure text specification for AI agent consumption

================================================================================
SECTION 1: EXECUTIVE SUMMARY
================================================================================

PURPOSE: Define how Baileys WhatsApp API writes inbound messages to shared PostgreSQL database.

KEY ARCHITECTURE PRINCIPLE: All messaging channels (WhatsApp, Email, Discord, Telegram) write to identical unified schema. No channel-specific message tables exist.

CORE REQUIREMENT: Baileys must normalize WhatsApp-specific data into standardized multi-channel schema.

================================================================================
SECTION 2: BUSINESS AND TENANCY MODEL
================================================================================

2.1 HIERARCHY STRUCTURE

Level 1: Tenant (Organization/Company)
Level 2: Workspace (Sales Campaign or Team within Tenant)
Level 3: Lead (Customer/Contact within Workspace)
Level 4: Conversation Thread (Message grouping per Lead and Channel)
Level 5: Messages (Individual messages across all channels)

2.2 TENANCY CONFIGURATION

TENANT IDENTIFIER: Integer tenant_id, auto-incrementing primary key
MULTIPLE WHATSAPP PER TENANT: Yes, unlimited at database level, package-limited at business level
SESSION SCOPE: Tenant-level (each session belongs to one tenant)

2.3 UNIQUENESS CONSTRAINTS

Channel Sessions Uniqueness: (tenant_id, channel_type, session_identifier)
Message Idempotency: (channel_session_id, channel_message_id)
Lead Uniqueness: (workspace_id, external_id)

================================================================================
SECTION 3: POSTGRESQL ENVIRONMENT
================================================================================

3.1 DATABASE SPECIFICATIONS

PostgreSQL Version: 15.x
Docker Image: postgres:15
Connection Method: Direct TCP connection, no connection pooler
Connection String Format: postgresql://user:password@host:port/database
Environment Variable: DATABASE_URL
Example Value: postgresql://user:password@db:5432/chatbot_db

3.2 SCHEMA MANAGEMENT

Migration Tool: None (SQLModel/SQLAlchemy Python ORM)
Schema Definition: Python SQLModel classes
Schema Creation: Automatic via create_all() method
Version Control: Application-managed, no Alembic or Flyway

3.3 POSTGRESQL EXTENSIONS

Required Extensions: None
Optional Available: pgcrypto (UUID generation), pg_trgm (fuzzy search)

================================================================================
SECTION 4: DATA MODEL - UNIFIED MULTI-CHANNEL SCHEMA
================================================================================

4.1 ARCHITECTURE DECISION

CRITICAL: System uses unified schema for ALL channels. No separate wa_messages, email_messages, discord_messages tables exist.

ALL channels write to same three core tables:
- et_channel_sessions (connection metadata)
- et_conversation_threads (conversation context)
- et_chat_messages (actual messages)

4.2 TABLE: et_channel_sessions

Purpose: Store connection metadata for each messaging channel

Column Definitions:
- id: INTEGER, SERIAL, PRIMARY KEY, NOT NULL
- tenant_id: INTEGER, FOREIGN KEY to et_tenants.id, NOT NULL, INDEXED
- channel_type: VARCHAR(50), NOT NULL, VALUES: whatsapp, email, discord, telegram
- session_identifier: VARCHAR(255), NOT NULL (phone number for WhatsApp, e.g. +60123456789)
- session_name: VARCHAR(255), NULL (human-readable name)
- status: VARCHAR(50), NOT NULL, DEFAULT active, VALUES: active, disconnected, suspended
- metadata: JSONB, DEFAULT {}, NULL (channel-specific configuration)
- created_at: TIMESTAMP, NOT NULL, DEFAULT NOW()
- last_connected_at: TIMESTAMP, NULL

Primary Key: id
Unique Constraint: (tenant_id, channel_type, session_identifier)
Indexes:
- idx_channel_sessions_tenant ON (tenant_id)
- idx_channel_sessions_status ON (status)

4.3 TABLE: et_conversation_threads

Purpose: Group messages into conversation context per lead and channel

Column Definitions:
- id: INTEGER, SERIAL, PRIMARY KEY, NOT NULL
- tenant_id: INTEGER, FOREIGN KEY to et_tenants.id, NOT NULL, INDEXED
- workspace_id: INTEGER, FOREIGN KEY to et_workspaces.id, NOT NULL, INDEXED
- lead_id: INTEGER, FOREIGN KEY to et_leads.id, NOT NULL, INDEXED
- channel_session_id: INTEGER, FOREIGN KEY to et_channel_sessions.id, NULL, INDEXED
- status: VARCHAR(50), NOT NULL, DEFAULT active, VALUES: active, archived, closed
- created_at: TIMESTAMP, NOT NULL, DEFAULT NOW()

Primary Key: id
Indexes:
- idx_threads_tenant ON (tenant_id)
- idx_threads_workspace ON (workspace_id)
- idx_threads_lead ON (lead_id)
- idx_threads_channel ON (channel_session_id)

4.4 TABLE: et_chat_messages

Purpose: Unified message storage for ALL channels (WhatsApp, Email, Discord, Telegram)

Column Definitions:
- id: INTEGER, SERIAL, PRIMARY KEY, NOT NULL
- tenant_id: INTEGER, FOREIGN KEY to et_tenants.id, NOT NULL, INDEXED
- thread_id: INTEGER, FOREIGN KEY to et_conversation_threads.id, NOT NULL, INDEXED
- channel_message_id: VARCHAR(255), NOT NULL, INDEXED (original message ID from channel)
- channel_timestamp: BIGINT, NOT NULL (Unix epoch milliseconds from channel)
- direction: VARCHAR(20), NOT NULL, INDEXED, VALUES: inbound, outbound
- role: VARCHAR(50), NOT NULL, VALUES: user, assistant, system
- sender_identifier: VARCHAR(255), NULL (phone/email of sender, e.g. +60123456789)
- message_type: VARCHAR(50), NOT NULL, DEFAULT text, VALUES: text, image, video, audio, document, reaction, deleted
- content: TEXT, NULL (text content, NULL for media-only messages)
- media_url: TEXT, NULL (URL to media file if applicable)
- media_metadata: JSONB, NULL (structure: {filename, mime_type, size, caption})
- raw_payload: JSONB, NULL (full original message object from channel)
- tool_calls: JSONB, NULL (AI tool calls for assistant messages)
- created_at: TIMESTAMP, NOT NULL, DEFAULT NOW(), INDEXED

Primary Key: id
Unique Constraint: (channel_session_id via thread, channel_message_id)
Note: Unique constraint enforced via application logic due to join requirement

Indexes:
- idx_messages_thread ON (thread_id)
- idx_messages_tenant ON (tenant_id)
- idx_messages_created ON (created_at DESC)
- idx_messages_channel_msg ON (channel_message_id)
- idx_messages_direction ON (direction)

4.5 TABLE: et_leads

Purpose: Customer/contact records (existing table, multi-channel extended)

Key Columns:
- id: INTEGER, PRIMARY KEY
- tenant_id: INTEGER, FOREIGN KEY to et_tenants.id
- workspace_id: INTEGER, FOREIGN KEY to et_workspaces.id
- external_id: VARCHAR, INDEXED (format: whatsapp:+60123456789, email:john@example.com)
- name: VARCHAR, NULL

Unique Constraint: (workspace_id, external_id)

4.6 MESSAGE IDEMPOTENCY RULE

Idempotency Key: (channel_session_id, channel_message_id)

Baileys must check message existence before insert using:
SELECT id FROM et_chat_messages WHERE thread_id = ? AND channel_message_id = ?

If row exists: Skip insertion, log duplicate, return success
If no row: Proceed with INSERT

Alternative SQL pattern:
INSERT INTO et_chat_messages (...) VALUES (...)
ON CONFLICT DO NOTHING (if unique index exists)

================================================================================
SECTION 5: MESSAGE CAPTURE REQUIREMENTS
================================================================================

5.1 INBOUND MESSAGE TYPES

Phase 1 MVP (implement now):
- text: Text messages
- image: Image files
- video: Video files
- audio: Voice notes and audio files
- document: PDF and document files

Phase 2 Future:
- reaction: Emoji reactions to messages
- edited: Edited message markers
- deleted: Deleted message markers

5.2 REQUIRED FIELD MAPPINGS (BAILEYS TO DATABASE)

Baileys Field -> Database Column -> Type -> Example

key.id -> channel_message_id -> VARCHAR(255) -> 3EB0XXXXX123
messageTimestamp -> channel_timestamp -> BIGINT -> 1708186800000 (multiply by 1000)
key.remoteJid -> sender_identifier -> VARCHAR(255) -> +60123456789 (normalized from 60123456789@s.whatsapp.net)
key.fromMe -> direction -> VARCHAR(20) -> false becomes inbound, true becomes outbound
key.fromMe -> role -> VARCHAR(50) -> false becomes user, true becomes assistant
message.conversation OR message.extendedTextMessage.text -> content -> TEXT -> Hello, I am interested
message type -> message_type -> VARCHAR(50) -> image (from message.imageMessage)
Full message object -> raw_payload -> JSONB -> Complete Baileys message structure

5.3 PHONE NUMBER NORMALIZATION

Input Format: 60123456789@s.whatsapp.net
Normalization Process:
1. Extract numeric portion before @ symbol: 60123456789
2. Prepend + symbol: +60123456789
3. Store in sender_identifier column

5.4 DIRECTION AND ROLE MAPPING

If key.fromMe equals false:
- direction = inbound
- role = user

If key.fromMe equals true:
- direction = outbound
- role = assistant

5.5 MEDIA HANDLING

For messages with media (image, video, audio, document):

Option A (Recommended for Production):
1. Baileys downloads media file
2. Baileys uploads to CDN (S3, CloudFlare R2, etc.)
3. Baileys stores CDN URL in media_url column
4. Baileys stores metadata in media_metadata column as JSON:
   {
     "filename": "invoice.jpg",
     "mime_type": "image/jpeg",
     "size": 245678,
     "caption": "Here is my invoice"
   }

Option B (MVP Temporary):
1. Baileys stores entire message in raw_payload column
2. Media access via raw_payload.message.imageMessage (or videoMessage, etc.)
3. Main SaaS processes media later

Implementation Choice: Start with Option B, migrate to Option A

================================================================================
SECTION 6: DELIVERY SEMANTICS
================================================================================

6.1 GUARANTEE LEVEL

Delivery Guarantee: At-least-once delivery at application level

Meaning:
- Messages may be written multiple times if Baileys crashes
- Duplicate writes prevented by unique constraint on (channel_session_id, channel_message_id)
- Duplicate attempts will fail silently without error
- Exactly-once delivery achieved through idempotency

6.2 DUPLICATE HANDLING

Acceptable Behavior: Duplicate write attempts are acceptable
PostgreSQL Response: Unique constraint violation (or ON CONFLICT DO NOTHING)
Baileys Response: Log duplicate attempt, continue processing, do not crash
Expected Duplicate Rate: Less than 0.1 percent (only during crashes/restarts)

6.3 MESSAGE ORDERING

Requirement: Messages must maintain chronological order per conversation thread

Implementation:
- Baileys writes messages ordered by channel_timestamp ascending
- If messages arrive out-of-order from WhatsApp, Baileys must buffer and sort before writing
- Database retrieval uses ORDER BY channel_timestamp ASC

6.4 WRITE LATENCY TARGETS

p95 Latency: Less than 500 milliseconds (receipt to commit)
p99 Latency: Less than 1 second
Timeout Threshold: 3 seconds
Retry Strategy: If write exceeds 3 seconds, retry with exponential backoff

================================================================================
SECTION 7: OWNERSHIP CONTRACT
================================================================================

7.1 TABLE WRITE PERMISSIONS

et_channel_sessions:
- Baileys: INSERT new sessions, UPDATE status and last_connected_at
- SaaS: Read-only

et_conversation_threads:
- Baileys: INSERT new threads (on first message from new channel)
- SaaS: INSERT new threads (manual creation), UPDATE status field
- Both: Read access

et_chat_messages:
- Baileys: INSERT messages with direction equals inbound
- SaaS: INSERT messages with direction equals outbound
- Both: Read access
- Neither: DELETE or UPDATE (append-only log)

et_leads:
- Baileys: SELECT for lookup, INSERT if lead does not exist
- SaaS: Full CRUD operations
- Baileys: Never UPDATE or DELETE

et_workspaces:
- Baileys: SELECT for lookup only
- SaaS: Full CRUD operations

et_tenants:
- Baileys: SELECT for lookup only
- SaaS: Full CRUD operations

7.2 THREAD CREATION LOGIC (CRITICAL)

Scenario 1: Inbound message from unknown contact

Step 1: Extract sender phone from key.remoteJid: 60123456789@s.whatsapp.net becomes +60123456789
Step 2: Construct external_id: whatsapp:+60123456789
Step 3: Query lead:
  SELECT id, workspace_id FROM et_leads 
  WHERE external_id = 'whatsapp:+60123456789' AND tenant_id = ?

Step 4a: If lead NOT found, create lead:
  INSERT INTO et_leads (tenant_id, workspace_id, external_id, name)
  VALUES (?, ?, 'whatsapp:+60123456789', '+60123456789')
  RETURNING id, workspace_id
  Note: workspace_id obtained from channel session metadata (see Section 7.3)

Step 4b: If lead found, use existing lead_id and workspace_id

Step 5: Query thread:
  SELECT id FROM et_conversation_threads
  WHERE lead_id = ? AND channel_session_id = ? AND status = 'active'

Step 6a: If thread NOT found, create thread:
  INSERT INTO et_conversation_threads (tenant_id, workspace_id, lead_id, channel_session_id)
  VALUES (?, ?, ?, ?)
  RETURNING id

Step 6b: If thread found, use existing thread_id

Step 7: Insert message into thread (see Section 8)

Scenario 2: Reply to existing conversation

Step 1: Lookup lead by external_id (as above)
Step 2: Lookup existing thread by lead_id and channel_session_id
Step 3: Insert message into existing thread

7.3 DEFAULT WORKSPACE ASSIGNMENT

Problem: When creating new lead, which workspace_id to assign?

Solution: Store default_workspace_id in channel session metadata

Database Storage:
UPDATE et_channel_sessions 
SET metadata = jsonb_set(metadata, '{default_workspace_id}', '10')
WHERE id = ?

Retrieval:
SELECT metadata-\>'default_workspace_id' AS workspace_id
FROM et_channel_sessions
WHERE id = ?

7.4 CONFLICT RESOLUTION RULES

Rule 1: Baileys never UPDATE or DELETE existing messages (append-only architecture)
Rule 2: If SaaS sets thread status to archived, Baileys creates NEW thread for next inbound message
Rule 3: Baileys never DELETE leads or workspaces under any circumstance

================================================================================
SECTION 8: COMPLETE MESSAGE INSERT ALGORITHM
================================================================================

Input: Baileys message object from WhatsApp webhook
Output: Message inserted into et_chat_messages table

ALGORITHM STEPS:

Step 1: Extract and normalize sender
  sender_jid = message.key.remoteJid
  sender_phone = extract_phone(sender_jid)  // 60123456789@s.whatsapp.net becomes +60123456789
  external_id = "whatsapp:" + sender_phone
  
Step 2: Find or create lead
  lead = SELECT id, workspace_id FROM et_leads 
         WHERE external_id = external_id AND tenant_id = tenant_id
  
  IF lead is NULL:
    workspace_id = get_default_workspace(channel_session_id)
    lead = INSERT INTO et_leads (tenant_id, workspace_id, external_id, name)
           VALUES (tenant_id, workspace_id, external_id, sender_phone)
           RETURNING id, workspace_id

Step 3: Find or create thread
  thread = SELECT id FROM et_conversation_threads
           WHERE lead_id = lead.id 
             AND channel_session_id = channel_session_id
             AND status = 'active'
  
  IF thread is NULL:
    thread = INSERT INTO et_conversation_threads 
             (tenant_id, workspace_id, lead_id, channel_session_id)
             VALUES (tenant_id, workspace_id, lead.id, channel_session_id)
             RETURNING id

Step 4: Check message idempotency
  channel_message_id = message.key.id
  existing = SELECT id FROM et_chat_messages
             WHERE thread_id = thread.id 
               AND channel_message_id = channel_message_id
  
  IF existing is NOT NULL:
    LOG: "Message already exists, skipping"
    RETURN success

Step 5: Extract message content
  message_type = determine_type(message)  // text, image, video, audio, document
  content = extract_content(message)      // text content or caption
  
Step 6: Determine direction and role
  direction = IF message.key.fromMe THEN 'outbound' ELSE 'inbound'
  role = IF message.key.fromMe THEN 'assistant' ELSE 'user'

Step 7: Insert message
  INSERT INTO et_chat_messages (
    tenant_id,
    thread_id,
    channel_message_id,
    channel_timestamp,
    direction,
    role,
    sender_identifier,
    message_type,
    content,
    raw_payload
  ) VALUES (
    tenant_id,
    thread.id,
    message.key.id,
    message.messageTimestamp * 1000,
    direction,
    role,
    sender_phone,
    message_type,
    content,
    JSON(message)  // Full message object as JSON
  )

Step 8: Return success

================================================================================
SECTION 9: SQL DDL SCHEMA DEFINITION
================================================================================

9.1 CREATE TABLE et_channel_sessions

CREATE TABLE IF NOT EXISTS et_channel_sessions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES et_tenants(id) ON DELETE CASCADE,
    channel_type VARCHAR(50) NOT NULL,
    session_identifier VARCHAR(255) NOT NULL,
    session_name VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_connected_at TIMESTAMP,
    CONSTRAINT uq_channel_session UNIQUE (tenant_id, channel_type, session_identifier)
);

CREATE INDEX idx_channel_sessions_tenant ON et_channel_sessions(tenant_id);
CREATE INDEX idx_channel_sessions_status ON et_channel_sessions(status);

9.2 CREATE TABLE et_conversation_threads

CREATE TABLE IF NOT EXISTS et_conversation_threads (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES et_tenants(id) ON DELETE CASCADE,
    workspace_id INTEGER NOT NULL REFERENCES et_workspaces(id) ON DELETE CASCADE,
    lead_id INTEGER NOT NULL REFERENCES et_leads(id) ON DELETE CASCADE,
    channel_session_id INTEGER REFERENCES et_channel_sessions(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_threads_tenant ON et_conversation_threads(tenant_id);
CREATE INDEX idx_threads_lead ON et_conversation_threads(lead_id);
CREATE INDEX idx_threads_workspace ON et_conversation_threads(workspace_id);
CREATE INDEX idx_threads_channel ON et_conversation_threads(channel_session_id);

9.3 CREATE TABLE et_chat_messages

CREATE TABLE IF NOT EXISTS et_chat_messages (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES et_tenants(id) ON DELETE CASCADE,
    thread_id INTEGER NOT NULL REFERENCES et_conversation_threads(id) ON DELETE CASCADE,
    channel_message_id VARCHAR(255) NOT NULL,
    channel_timestamp BIGINT NOT NULL,
    direction VARCHAR(20) NOT NULL,
    role VARCHAR(50) NOT NULL,
    sender_identifier VARCHAR(255),
    message_type VARCHAR(50) NOT NULL DEFAULT 'text',
    content TEXT,
    media_url TEXT,
    media_metadata JSONB,
    raw_payload JSONB,
    tool_calls JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_thread ON et_chat_messages(thread_id);
CREATE INDEX idx_messages_tenant ON et_chat_messages(tenant_id);
CREATE INDEX idx_messages_created ON et_chat_messages(created_at DESC);
CREATE INDEX idx_messages_channel_msg ON et_chat_messages(channel_message_id);
CREATE INDEX idx_messages_direction ON et_chat_messages(direction);

Note: Unique constraint on (channel_session_id, channel_message_id) enforced via application logic

================================================================================
SECTION 10: SAMPLE DATA
================================================================================

10.1 SAMPLE et_channel_sessions

INSERT INTO et_channel_sessions VALUES
(1, 101, 'whatsapp', '+60123456789', 'Sales Team WhatsApp', 'active', '{"device":"iPhone 14","default_workspace_id":10}', '2026-02-01 10:00:00', '2026-02-17 09:00:00'),
(2, 101, 'email', 'sales@company.com', 'Sales Email', 'active', '{"provider":"Gmail","default_workspace_id":10}', '2026-02-01 10:05:00', '2026-02-17 09:05:00'),
(3, 102, 'whatsapp', '+60198765432', 'Support WhatsApp', 'active', '{"device":"Android","default_workspace_id":20}', '2026-02-02 09:00:00', '2026-02-17 08:30:00');

10.2 SAMPLE et_conversation_threads

INSERT INTO et_conversation_threads VALUES
(1, 101, 10, 1001, 1, 'active', '2026-02-10 14:00:00'),
(2, 101, 10, 1002, 1, 'active', '2026-02-11 09:30:00'),
(3, 102, 20, 2001, 3, 'archived', '2026-02-05 08:00:00');

10.3 SAMPLE et_chat_messages

INSERT INTO et_chat_messages VALUES
(1, 101, 1, '3EB0ABC123', 1708170000000, 'inbound', 'user', '+60111222333', 'text', 'Hello, I need help', NULL, NULL, '{"key":{"id":"3EB0ABC123","remoteJid":"60111222333@s.whatsapp.net","fromMe":false},"message":{"conversation":"Hello, I need help"},"messageTimestamp":1708170000}', NULL, '2026-02-10 14:00:05'),
(2, 101, 1, '3EB0DEF456', 1708170120000, 'outbound', 'assistant', '+60123456789', 'text', 'Sure! How can I assist?', NULL, NULL, '{}', NULL, '2026-02-10 14:02:15'),
(3, 101, 2, '3EB0GHI789', 1708256400000, 'inbound', 'user', '+60222333444', 'image', 'Check this invoice', NULL, '{"filename":"invoice.jpg","mime_type":"image/jpeg","size":125000,"caption":"Check this invoice"}', '{"key":{"id":"3EB0GHI789"},"message":{"imageMessage":{"caption":"Check this invoice"}}}', NULL, '2026-02-11 09:31:00');

10.4 SAMPLE et_leads

INSERT INTO et_leads VALUES
(1001, 101, 10, 'whatsapp:+60111222333', 'John Doe', '2026-02-10 13:59:00'),
(1002, 101, 10, 'whatsapp:+60222333444', 'Jane Smith', '2026-02-11 09:29:00'),
(2001, 102, 20, 'whatsapp:+60333444555', 'Ali Rahman', '2026-02-05 07:58:00');

================================================================================
SECTION 11: QUERY PATTERNS FOR SAAS SYSTEM
================================================================================

11.1 QUERY: Get conversation history for lead

SELECT m.* 
FROM et_chat_messages m
JOIN et_conversation_threads t ON m.thread_id = t.id
WHERE t.lead_id = 123 
  AND t.status = 'active'
ORDER BY m.channel_timestamp ASC
LIMIT 100;

11.2 QUERY: Get recent inbound messages for processing

SELECT m.*, t.lead_id, t.workspace_id
FROM et_chat_messages m
JOIN et_conversation_threads t ON m.thread_id = t.id
WHERE m.direction = 'inbound'
  AND m.created_at > NOW() - INTERVAL '5 minutes'
  AND t.tenant_id = 123
ORDER BY m.created_at DESC;

11.3 QUERY: Find lead by phone number

SELECT * FROM et_leads
WHERE external_id = 'whatsapp:+60123456789'
  AND tenant_id = 123;

11.4 QUERY: Get active WhatsApp sessions for tenant

SELECT * FROM et_channel_sessions
WHERE tenant_id = 123
  AND channel_type = 'whatsapp'
  AND status = 'active';

11.5 QUERY: Count messages per lead

SELECT t.lead_id, COUNT(m.id) as message_count
FROM et_chat_messages m
JOIN et_conversation_threads t ON m.thread_id = t.id
WHERE t.tenant_id = 123
GROUP BY t.lead_id
ORDER BY message_count DESC;

11.6 QUERY: Search messages by content

SELECT m.*, t.lead_id
FROM et_chat_messages m
JOIN et_conversation_threads t ON m.thread_id = t.id
WHERE m.content ILIKE '%invoice%'
  AND t.tenant_id = 123
ORDER BY m.created_at DESC
LIMIT 50;

11.7 QUERY: Get unread messages since last AI reply

WITH last_ai_message AS (
  SELECT thread_id, MAX(created_at) as last_reply_time
  FROM et_chat_messages
  WHERE role = 'assistant' AND thread_id = 123
  GROUP BY thread_id
)
SELECT m.*
FROM et_chat_messages m
LEFT JOIN last_ai_message l ON m.thread_id = l.thread_id
WHERE m.thread_id = 123
  AND m.direction = 'inbound'
  AND (m.created_at > l.last_reply_time OR l.last_reply_time IS NULL);

11.8 QUERY: Get media messages only

SELECT * FROM et_chat_messages
WHERE thread_id = 123
  AND message_type IN ('image', 'video', 'document', 'audio')
ORDER BY created_at DESC;

11.9 QUERY: Daily message volume per workspace

SELECT t.workspace_id, DATE(m.created_at) as message_date, COUNT(*) as message_count
FROM et_chat_messages m
JOIN et_conversation_threads t ON m.thread_id = t.id
WHERE t.tenant_id = 123
GROUP BY t.workspace_id, DATE(m.created_at)
ORDER BY message_date DESC;

11.10 QUERY: Find threads awaiting AI reply

SELECT DISTINCT t.id, t.lead_id
FROM et_conversation_threads t
JOIN et_chat_messages m ON m.thread_id = t.id
WHERE t.tenant_id = 123
  AND m.direction = 'inbound'
  AND NOT EXISTS (
    SELECT 1 FROM et_chat_messages m2 
    WHERE m2.thread_id = t.id AND m2.role = 'assistant'
  );

================================================================================
SECTION 12: PERFORMANCE AND SCALE EXPECTATIONS
================================================================================

12.1 EXPECTED VOLUME

Daily Message Volume MVP: 10,000 to 50,000 messages per day (100 tenants)
Peak Throughput MVP: 10 to 20 messages per second
Scaling Target: 1,000,000 messages per day (1000 tenants)

12.2 PAGINATION AND SORTING

All message queries must use ORDER BY channel_timestamp or created_at
Pagination method: LIMIT and OFFSET or cursor-based WHERE id > last_id
Default sort order: Chronological ascending for conversation history

================================================================================
SECTION 13: SECURITY AND COMPLIANCE
================================================================================

13.1 PII POLICY

Phone Numbers: Stored in plain text (required for operations)
Message Content: Stored in plain text (required for AI processing)
Retention Period: Indefinite (user-controlled deletion via SaaS UI)

13.2 ENCRYPTION

Database Level: PostgreSQL host encryption (Railway or AWS RDS managed)
Column Level: Not required for MVP
Future Consideration: Encrypt content column if GDPR strict mode required

13.3 AUDIT LOGGING

Requirement: All write operations logged for debugging

Baileys Logging:
- Timestamp of operation
- tenant_id
- channel_session_id
- message_id
- Action: INSERT, UPDATE, or SELECT
- Result: success or failure
- Error message if applicable

Log Format: Structured JSON
Log Destination: STDOUT or separate audit table (wa_audit_log)

================================================================================
SECTION 14: MONITORING AND OPERATIONS
================================================================================

14.1 METRICS REQUIREMENTS

Baileys must expose Prometheus-compatible metrics on /metrics endpoint:

Metric: wa_messages_received_total
Type: Counter
Labels: tenant_id
Description: Total messages received from WhatsApp

Metric: wa_messages_written_total
Type: Counter
Labels: tenant_id
Description: Total messages written to database

Metric: wa_write_errors_total
Type: Counter
Labels: tenant_id, error_type
Description: Total write errors (unique_violation, timeout, connection_error)

Metric: wa_write_latency_seconds
Type: Histogram
Labels: tenant_id
Buckets: 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0
Description: Message write latency distribution

Metric: wa_sessions_active
Type: Gauge
Labels: tenant_id
Description: Number of active WhatsApp sessions

14.2 ALERT THRESHOLDS

Alert: High Error Rate
Condition: wa_write_errors_total rate > 1 percent for 5 minutes
Severity: Warning

Alert: High Latency
Condition: wa_write_latency_seconds p99 > 2 seconds for 10 minutes
Severity: Warning

Alert: Session Disconnected
Condition: Session status = disconnected for > 30 minutes
Severity: Critical

14.3 HEALTH CHECK ENDPOINT

Endpoint: GET /health

Response Format:
{
  "status": "ok",
  "database": "connected",
  "platform": "connected",
  "timestamp": "2026-02-17T14:30:00Z"
}

Status Values: ok, degraded, error

Database Check: Execute SELECT 1 query with 5 second timeout
Platform Check: Verify WhatsApp connection active

14.4 DISASTER RECOVERY

RPO (Recovery Point Objective): 5 minutes (acceptable data loss window)
RTO (Recovery Time Objective): 30 minutes (maximum downtime)
Backup: PostgreSQL daily snapshots (Railway or AWS automated)
Baileys Recovery: On restart, resume from last processed message using WhatsApp message history API

================================================================================
SECTION 15: BAILEYS IMPLEMENTATION CHECKLIST
================================================================================

15.1 PHASE 1 MVP (REQUIRED FOR LAUNCH)

Task: Connect to PostgreSQL using DATABASE_URL environment variable
Status: Required

Task: Extract sender phone number from message.key.remoteJid and normalize to +60123456789 format
Status: Required

Task: Lookup or create lead with external_id = whatsapp:+phone
Status: Required

Task: Lookup or create conversation thread for lead and channel session
Status: Required

Task: Check message idempotency (query by thread_id and channel_message_id)
Status: Required

Task: Insert message into et_chat_messages with all required fields
Status: Required

Task: Handle PostgreSQL unique constraint violations gracefully without crash
Status: Required

Task: Support message types: text, image, video, audio, document
Status: Required

Task: Store full raw Baileys message in raw_payload JSONB column
Status: Required

Task: Expose Prometheus metrics on /metrics endpoint
Status: Required

Task: Expose health check on /health endpoint
Status: Required

Task: Log all database operations with structured JSON logging
Status: Required

15.2 PHASE 2 PRODUCTION HARDENING

Task: Implement retry logic with exponential backoff (maximum 3 retries)
Status: Recommended

Task: Add circuit breaker for PostgreSQL connection failures
Status: Recommended

Task: Implement media upload to CDN (currently using raw_payload)
Status: Future

Task: Support message reactions, edits, and deletions
Status: Future

Task: Implement webhook parallel writes as backup
Status: Optional

15.3 REQUIRED API ENDPOINTS

Endpoint: POST /send
Purpose: Send outbound WhatsApp messages
Request Body:
{
  "tenant_id": 101,
  "channel_session_id": 1,
  "recipient": "+60123456789",
  "message_type": "text",
  "content": "Hello from AI assistant",
  "media_url": "https://cdn.example.com/file.jpg"
}
Response:
{
  "success": true,
  "channel_message_id": "3EB0XYZ789",
  "sent_at": 1708186800000
}

Endpoint: GET /health
Purpose: Health check for monitoring
Response: See Section 14.3

Endpoint: GET /sessions/:tenant_id
Purpose: List active WhatsApp sessions for tenant
Response:
[
  {
    "session_id": 1,
    "channel_type": "whatsapp",
    "identifier": "+60123456789",
    "status": "active",
    "last_connected": "2026-02-17T10:00:00Z"
  }
]

Endpoint: POST /webhook/:tenant_id/:session_id
Purpose: Receive inbound WhatsApp messages from WhatsApp Cloud API
Request Body: WhatsApp message payload
Response: {"received": true}

================================================================================
SECTION 16: OPEN QUESTIONS FOR BAILEYS TEAM
================================================================================

Question 1: Session Management and QR Code
How will WhatsApp session initialization work?
Does Baileys need to expose an API endpoint for QR code generation?
Where are WhatsApp session tokens stored (in metadata column)?

Question 2: Webhook Tenant and Session Identification
How does Baileys identify tenant_id and channel_session_id from incoming webhook?
Proposed solution: Webhook URL includes identifiers: /webhook/:tenant_id/:session_id
Alternative: Lookup by phone number mapping

Question 3: Database Connection Failure Retry Strategy
What happens when PostgreSQL is temporarily unavailable?
Options:
- Buffer messages in memory (risk of data loss on crash)
- Write to local disk queue (requires persistence layer)
- Drop messages after X retry attempts (data loss acceptable?)
Recommended: Disk queue with retry

Question 4: Rate Limiting Per Tenant
Should Baileys enforce write rate limits (e.g. maximum 100 messages per second per tenant)?
Or trust PostgreSQL to handle load?

Question 5: Backfill Historical Messages
Will Baileys need to import historical WhatsApp messages?
If yes, provide API endpoint for bulk message insert with custom timestamps

================================================================================
SECTION 17: TESTING SCENARIOS
================================================================================

17.1 TEST SCENARIO: New unknown sender

Steps:
1. Send WhatsApp message from new phone number +60111222333 not in database
2. Verify Baileys creates lead with external_id = whatsapp:+60111222333
3. Verify Baileys creates conversation thread
4. Verify message inserted into et_chat_messages

Validation SQL:
SELECT * FROM et_leads WHERE external_id = 'whatsapp:+60111222333';
SELECT * FROM et_conversation_threads WHERE lead_id = (previous result);
SELECT * FROM et_chat_messages WHERE thread_id = (previous result);

Expected Result: One lead, one thread, one message

17.2 TEST SCENARIO: Reply to existing conversation

Steps:
1. Send another WhatsApp message from same phone number +60111222333
2. Verify Baileys finds existing lead
3. Verify Baileys finds existing thread
4. Verify message appended to same thread

Validation SQL:
SELECT COUNT(*) FROM et_chat_messages 
WHERE thread_id = (thread_id from test 17.1)
AND sender_identifier = '+60111222333';

Expected Result: Two messages in same thread

17.3 TEST SCENARIO: Duplicate message idempotency

Steps:
1. Simulate Baileys crash by sending same message twice with identical channel_message_id
2. Verify first insert succeeds
3. Verify second insert is skipped (idempotency check)

Validation SQL:
SELECT COUNT(*) FROM et_chat_messages 
WHERE channel_message_id = '3EB0TEST123';

Expected Result: Exactly one message (no duplicate)

17.4 TEST SCENARIO: Media message with caption

Steps:
1. Send WhatsApp image message with caption "This is my invoice"
2. Verify message_type = image
3. Verify content = "This is my invoice"
4. Verify raw_payload contains imageMessage object

Validation SQL:
SELECT message_type, content, raw_payload->\'message\'->\'imageMessage\' 
FROM et_chat_messages 
WHERE channel_message_id = 'IMAGE_MSG_ID';

Expected Result: Correct message_type, caption in content, raw payload preserved

17.5 TEST SCENARIO: High volume stress test

Steps:
1. Send 1000 messages from 100 different senders within 60 seconds
2. Verify all messages inserted without errors
3. Verify write latency p95 < 500ms
4. Verify no duplicate messages

Validation SQL:
SELECT COUNT(*) FROM et_chat_messages 
WHERE created_at > NOW() - INTERVAL '2 minutes';

SELECT COUNT(DISTINCT channel_message_id) FROM et_chat_messages
WHERE created_at > NOW() - INTERVAL '2 minutes';

Expected Result: Both counts equal 1000, no duplicates, latency target met

================================================================================
SECTION 18: ENVIRONMENT CONFIGURATION
================================================================================

18.1 REQUIRED ENVIRONMENT VARIABLES

DATABASE_URL
Description: PostgreSQL connection string
Format: postgresql://user:password@host:port/database
Example: postgresql://user:password@db:5432/chatbot_db
Required: Yes

PORT
Description: HTTP server port for Baileys API
Example: 3000
Required: Yes

WHATSAPP_SESSION_DIR
Description: Directory for WhatsApp session storage
Example: /app/sessions
Required: Yes (Baileys specific)

LOG_LEVEL
Description: Logging verbosity
Values: debug, info, warn, error
Default: info
Required: No

NODE_ENV
Description: Application environment
Values: development, staging, production
Default: production
Required: No

================================================================================
SECTION 19: CONTACT AND TIMELINE
================================================================================

19.1 IMPLEMENTATION TIMELINE

Week 1: Baileys team reviews specification and asks clarifying questions
Week 2: Baileys implements MVP text message handling
Week 3: Testing with staging database (1 tenant, 1 session, 100 messages)
Week 4: Add media support (image, video, audio, document types)
Week 5: Load testing (1000 messages per second, 10 concurrent sessions)
Week 6: Production launch

19.2 DATABASE ACCESS

Staging Database: To be provided by AIworkforMe team
Production Database: To be provided after successful staging testing

19.3 COMMUNICATION CHANNELS

Technical Questions: To be specified by AIworkforMe team
Issue Reporting: To be specified by AIworkforMe team
Documentation Updates: Via git repository

================================================================================
END OF SPECIFICATION
================================================================================

Document Version: 1.0
Last Updated: 2026-02-17
Status: Ready for Baileys AI Agent Implementation
Total Sections: 19
