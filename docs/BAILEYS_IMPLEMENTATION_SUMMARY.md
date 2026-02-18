# Baileys Integration - Implementation Summary

**Date:** 2026-02-17  
**Status:** Ready for Baileys Team  

---

## What You Have Now

### 📄 Documentation Created

1. **`BAILEYS_INTEGRATION_SPEC.md`** (Main Spec - 500+ lines)
   - Complete PostgreSQL integration specification for Baileys team
   - 17 sections covering everything from database schema to operations
   - Includes SQL DDL, sample data, ERD, and implementation checklist
   - Can be sent directly to Baileys team

2. **`CHANNEL_API_ARCHITECTURE.md`** (Architecture Overview)
   - Explains the "Signal Transmission Tower" concept
   - Shows how ALL channel servers (WhatsApp/Discord/Telegram/Email) integrate
   - Reusable pattern for future Channel API Servers
   - Deployment strategy and monitoring guidelines

3. **Updated Database Models:**
   - `channel_models.py` - New ChannelSession model
   - `crm_models.py` - Extended with multi-channel fields

---

## Architecture Summary

```
┌─────────────────────────────────────────────┐
│  Your Main SaaS (AIworkforMe Backend)       │
│  - CRM, Leads, Workspaces                   │
│  - AI Workflow Engine                       │
│  - Outbound Message Router                  │
└────────────┬────────────────────────────────┘
             │
    ┌────────▼────────┐
    │   PostgreSQL    │  ◄── Unified Schema (ALL channels)
    │   (Shared DB)   │
    └────┬─────┬──────┘
         │     │
    ┌────▼──┐ ┌▼────────┐
    │Baileys│ │Discord  │  ◄── Signal Transmission Towers
    │ (WA)  │ │(Future) │      (Separate services on Railway)
    └───┬───┘ └─────────┘
        │
    ┌───▼────┐
    │WhatsApp│
    └────────┘
```

---

## Key Design Decisions

### ✅ Unified Schema (NOT Channel-Specific Tables)
- **All** messaging channels write to the SAME tables
- No separate `wa_messages`, `discord_messages`, etc.
- One conversation history regardless of channel

**Tables:**
- `et_channel_sessions` - Connection metadata (WhatsApp sessions, Discord bots, etc.)
- `et_conversation_threads` - Conversation context per lead
- `et_chat_messages` - Unified message storage

### ✅ Channel API Servers as Independent Services
- Baileys (WhatsApp) = Separate Railway service
- Future Discord API = Separate Railway service
- Each connects to shared PostgreSQL
- Each follows the same integration pattern

### ✅ Bidirectional Message Flow
**Inbound:**
```
WhatsApp → Baileys → PostgreSQL → AI Workflow
```

**Outbound:**
```
AI → Outbound Router → Baileys API → WhatsApp
```

---

## What Baileys Team Needs to Do

### Phase 1: MVP Implementation
1. **Connect to PostgreSQL**
   - Use `DATABASE_URL` environment variable
   - Connect to shared database

2. **On Message Received (Webhook):**
   - Normalize phone number: `60123456789@s.whatsapp.net` → `+60123456789`
   - Lookup/create lead with `external_id = "whatsapp:+60123456789"`
   - Lookup/create conversation thread
   - Insert message into `et_chat_messages` with all required fields
   - Handle duplicate messages gracefully (unique constraint)

3. **Support Message Types:**
   - Text, image, video, audio, document
   - Store full raw payload in `raw_payload` JSONB column

4. **Expose API Endpoints:**
   - `POST /send` - Send outbound messages
   - `GET /health` - Health check
   - `GET /sessions/:tenant_id` - List active sessions

5. **Monitoring:**
   - Prometheus metrics on `/metrics`
   - Structured JSON logs

### Key Fields to Populate

| Database Column | From Baileys |
|----------------|--------------|
| `channel_message_id` | `message.key.id` |
| `channel_timestamp` | `messageTimestamp * 1000` |
| `sender_identifier` | Normalized phone: `+60123456789` |
| `direction` | `fromMe=false` → `inbound` |
| `role` | `inbound` → `user`, `outbound` → `assistant` |
| `message_type` | `text`, `image`, `video`, etc. |
| `content` | Text content from message |
| `raw_payload` | Full Baileys message object (JSONB) |

---

## Idempotency Strategy

**Problem:** Baileys might crash and resend the same message

**Solution:** Check if message already exists before inserting

```javascript
// Pseudocode
const existing = await db.query(
  'SELECT id FROM et_chat_messages WHERE thread_id = $1 AND channel_message_id = $2',
  [threadId, messageId]
);

if (existing) {
  console.log('Message already exists, skipping');
  return;
}

await db.query('INSERT INTO et_chat_messages (...) VALUES (...)');
```

---

## Database Schema Changes Needed

Run these migrations on your PostgreSQL:

```sql
-- 1. Create channel sessions table
CREATE TABLE et_channel_sessions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES et_tenants(id),
    channel_type VARCHAR(50) NOT NULL,
    session_identifier VARCHAR(255) NOT NULL,
    session_name VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_connected_at TIMESTAMP,
    UNIQUE (tenant_id, channel_type, session_identifier)
);

CREATE INDEX idx_channel_sessions_tenant ON et_channel_sessions(tenant_id);

-- 2. Extend conversation threads
ALTER TABLE et_conversation_threads 
ADD COLUMN channel_session_id INTEGER REFERENCES et_channel_sessions(id);

CREATE INDEX idx_threads_channel ON et_conversation_threads(channel_session_id);

-- 3. Extend chat messages (SIGNIFICANT CHANGES)
ALTER TABLE et_chat_messages 
ADD COLUMN channel_message_id VARCHAR(255) NOT NULL DEFAULT 'legacy',
ADD COLUMN channel_timestamp BIGINT,
ADD COLUMN direction VARCHAR(20),
ADD COLUMN sender_identifier VARCHAR(255),
ADD COLUMN message_type VARCHAR(50) DEFAULT 'text',
ADD COLUMN media_url TEXT,
ADD COLUMN media_metadata JSONB,
ADD COLUMN raw_payload JSONB;

UPDATE et_chat_messages SET 
  channel_timestamp = EXTRACT(EPOCH FROM created_at) * 1000,
  direction = CASE role WHEN 'user' THEN 'inbound' ELSE 'outbound' END
WHERE channel_timestamp IS NULL;

ALTER TABLE et_chat_messages 
ALTER COLUMN channel_timestamp SET NOT NULL,
ALTER COLUMN direction SET NOT NULL,
ALTER COLUMN content DROP NOT NULL;  -- Allow NULL for media-only messages

CREATE INDEX idx_messages_channel_msg ON et_chat_messages(channel_message_id);
CREATE INDEX idx_messages_direction ON et_chat_messages(direction);
```

**⚠️ WARNING:** The `et_chat_messages` changes are breaking if you have existing data. You'll need to migrate old messages.

---

## Next Steps for You (Main Backend Team)

### 1. Database Migration
- [ ] Review the SQL migrations above
- [ ] Test on staging database first
- [ ] Run migrations on production
- [ ] Update SQLModel models (already done in crm_models.py)

### 2. Import ChannelSession Model
Add to your database initialization:

```python
# In backend/src/infra/database.py or main.py
from src.adapters.db.channel_models import ChannelSession

# Make sure it's included in create_all()
```

### 3. Create Outbound Message Router (Future)
This service will:
- Poll `et_chat_messages` for messages with `direction='outbound'` and `sent_at IS NULL`
- Determine which channel (based on thread's `channel_session_id`)
- Call appropriate Channel API: `POST https://baileys-api.railway.app/send`

### 4. Implement DB Trigger/Polling for Inbound Messages
```python
# Pseudocode for workflow trigger
while True:
    new_messages = db.query("""
        SELECT * FROM et_chat_messages 
        WHERE direction = 'inbound' 
          AND processed_at IS NULL
        ORDER BY created_at ASC
        LIMIT 100
    """)
    
    for msg in new_messages:
        trigger_ai_workflow(msg)
        mark_as_processed(msg.id)
    
    sleep(5)
```

---

## Testing Plan

### Test Scenario 1: New Lead (Unknown Sender)
1. Send WhatsApp message from new number `+60111222333`
2. Baileys creates lead with `external_id = "whatsapp:+60111222333"`
3. Baileys creates conversation thread
4. Message inserted into `et_chat_messages`

**Verify:**
```sql
SELECT * FROM et_leads WHERE external_id = 'whatsapp:+60111222333';
SELECT * FROM et_conversation_threads WHERE lead_id = <above_id>;
SELECT * FROM et_chat_messages WHERE thread_id = <above_id>;
```

### Test Scenario 2: Reply to Existing Conversation
1. Send another message from same number
2. Baileys finds existing lead and thread
3. Message appended to same thread

**Verify:**
```sql
SELECT COUNT(*) FROM et_chat_messages WHERE thread_id = <thread_id>;
-- Should be 2 messages
```

### Test Scenario 3: Duplicate Message (Idempotency)
1. Simulate Baileys crash - resend same message twice
2. Second insert should be skipped
3. No duplicate in database

**Verify:**
```sql
SELECT COUNT(*) FROM et_chat_messages 
WHERE channel_message_id = '3EB0ABC123';
-- Should still be 1
```

### Test Scenario 4: Media Message
1. Send image with caption via WhatsApp
2. Verify `message_type = 'image'`
3. Verify `raw_payload` contains image data
4. Verify `content` contains caption

---

## Open Questions to Resolve

### For Baileys Team:
**Q1:** How are you handling session initialization?
- Do we need to provide QR code generation endpoint?
- Where do you store WhatsApp session tokens?

**Q2:** Tenant/Session identification in webhooks
- How does Baileys know which `tenant_id` and `channel_session_id`?
- Proposed: `/webhook/:tenant_id/:session_id`

**Q3:** Default workspace assignment
- When creating a new lead, which `workspace_id` to use?
- Proposed: Store in `et_channel_sessions.metadata.default_workspace_id`

### For Your Team:
**Q4:** Existing chat data migration
- Do you have existing messages in `et_chat_messages` that need to be preserved?
- If yes, we need a migration script to populate new fields

**Q5:** Outbound message triggering
- Will you implement polling or PostgreSQL NOTIFY/LISTEN?
- Performance target (latency for AI reply)?

---

## Communication Plan

### With Baileys Team
1. **Send them:** `BAILEYS_INTEGRATION_SPEC.md`
2. **Schedule:** Kickoff call to walk through spec (30 min)
3. **Provide:** Staging database credentials
4. **Set up:** Shared Slack channel for questions

### Internal (Your Team)
1. **Review:** Database migration plan (discuss breaking changes)
2. **Implement:** Outbound message router (Priority: Medium)
3. **Implement:** Inbound message workflow trigger (Priority: High)
4. **Test:** End-to-end flow with Baileys staging environment

---

## Timeline Estimate

| Week | Baileys Team | Your Team |
|------|-------------|-----------|
| 1 | Review spec, ask questions | Run database migrations (staging) |
| 2 | Implement text messages MVP | Implement inbound workflow trigger |
| 3 | Test with staging DB | Test integration end-to-end |
| 4 | Add media support | Implement outbound router |
| 5 | Load testing | Performance tuning |
| 6 | Production deployment | Production launch |

---

## Success Criteria

For MVP to be considered DONE:
- [ ] Baileys receives WhatsApp message → writes to PostgreSQL
- [ ] Unknown sender auto-creates lead
- [ ] Messages grouped into conversation threads
- [ ] Duplicate messages handled (idempotency works)
- [ ] Text messages work end-to-end
- [ ] Image messages work with caption
- [ ] Your AI can read messages and generate replies
- [ ] Outbound messages sent via Baileys API
- [ ] No data loss over 24-hour test period
- [ ] p95 latency < 500ms for message insert

---

## Files to Share with Baileys Team

**Send these files:**
1. `docs/BAILEYS_INTEGRATION_SPEC.md` ⭐ (Main spec)
2. `docs/CHANNEL_API_ARCHITECTURE.md` (Context)
3. Sample database credentials (staging)

**Optional (for reference):**
- `backend/src/adapters/db/crm_models.py` (Show actual SQLModel definitions)
- `backend/src/adapters/db/channel_models.py` (ChannelSession model)

---

## Summary: What Makes This Design Good

✅ **Unified Schema** - One conversation history for all channels (WhatsApp, Email, Discord, Telegram)  
✅ **Scalable** - Independent Channel API Servers, horizontally scalable  
✅ **Idempotent** - Duplicate messages handled gracefully  
✅ **Extensible** - Easy to add new channels (just follow the template)  
✅ **Observable** - Metrics and logs baked in  
✅ **Resilient** - At-least-once delivery with deduplication  

---

**End of Summary**

Next actions:
1. Send `BAILEYS_INTEGRATION_SPEC.md` to Baileys team
2. Schedule kickoff call
3. Run database migrations on staging
4. Start parallel development (Baileys + Your workflow engine)
