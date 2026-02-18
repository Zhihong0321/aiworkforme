# Channel API Architecture - Signal Transmission Towers

Project: AIworkforMe Multi-Channel Sales AI Agent
Date: 2026-02-18
Status: Final Design

---

## Overview

AIworkforMe uses independent Channel API Servers (Signal Transmission Towers) to relay messages between messaging platforms and shared PostgreSQL database.

Each Channel API Server:
- Independent service (separate codebase, separate deployment)
- Hosted on Railway (same cluster as main SaaS)
- Shares PostgreSQL database
- Handles both inbound (receive) and outbound (send) messages

---

## Architecture

```
Main SaaS Backend (Python/FastAPI)
- CRM, Leads, Workspaces
- AI Workflow Engine
- Outbound Message Router

        |
        v
        
PostgreSQL 15 (Shared Database)
- et_threads (conversation threads)
- et_messages (ALL messages, inbound + outbound)

        ^
        |
        
Channel API Servers (Signal Transmission Towers):
- Baileys API (WhatsApp) - Node.js
- Discord API (Future) - TBD
- Telegram API (Future) - TBD
- Email API (Future) - TBD

        |
        v
        
External Platforms:
- WhatsApp Cloud API
- Discord API
- Telegram API
- SMTP/IMAP Servers
```

---

## Database Schema

### Table 1: et_threads

```sql
CREATE TABLE et_threads (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    lead_id INTEGER NOT NULL,
    channel VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Purpose: Groups messages into conversation threads
Management: Auto-created by PostgreSQL trigger
One active thread per (lead_id, channel)

### Table 2: et_messages

```sql
CREATE TABLE et_messages (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    lead_id INTEGER NOT NULL,
    thread_id INTEGER,
    channel VARCHAR(50) NOT NULL,
    message_id VARCHAR(255) NOT NULL,
    timestamp BIGINT NOT NULL,
    direction VARCHAR(20) NOT NULL,
    message_type VARCHAR(50) NOT NULL DEFAULT 'text',
    text_content TEXT,
    media_url TEXT,
    raw_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    UNIQUE(channel, lead_id, message_id)
);
```

Purpose: Stores ALL messages (inbound from customers, outbound from AI)
Direction values: "inbound", "outbound"
Thread assignment: Automatic via trigger

---

## Thread Management (Automatic)

PostgreSQL trigger automatically assigns thread_id to new messages:

```sql
CREATE OR REPLACE FUNCTION assign_thread()
RETURNS TRIGGER AS $$
DECLARE
    v_thread_id INTEGER;
BEGIN
    SELECT id INTO v_thread_id
    FROM et_threads
    WHERE lead_id = NEW.lead_id 
      AND channel = NEW.channel
      AND status = 'active'
    LIMIT 1;
    
    IF v_thread_id IS NULL THEN
        INSERT INTO et_threads (tenant_id, lead_id, channel)
        VALUES (NEW.tenant_id, NEW.lead_id, NEW.channel)
        RETURNING id INTO v_thread_id;
    END IF;
    
    NEW.thread_id := v_thread_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_assign_thread
BEFORE INSERT ON et_messages
FOR EACH ROW
EXECUTE FUNCTION assign_thread();
```

Channel APIs don't need to manage threads - just insert messages.

---

## Channel API Responsibilities

### Inbound Message Flow

1. Platform sends message to Channel API webhook
2. Channel API normalizes message
3. Channel API checks for duplicate (query by message_id)
4. If duplicate: skip and log
5. If new: INSERT into et_messages with direction='inbound'
6. Trigger auto-assigns thread_id
7. Return success to platform

Example:
```
Customer sends WhatsApp → Baileys webhook → INSERT et_messages → Trigger creates/assigns thread → Done
```

### Outbound Message Flow

1. Main Backend AI generates reply
2. Main Backend INSERTs into et_messages with direction='outbound'
3. Outbound Router queries pending outbound messages
4. Outbound Router calls Channel API POST /send endpoint
5. Channel API sends via platform
6. Channel API updates message with delivery status

Example:
```
AI generates reply → INSERT et_messages (outbound) → Outbound Router → Baileys POST /send → WhatsApp
```

---

## What Channel APIs Must Implement

### Required: Message Insert (Inbound)

```javascript
// Pseudocode for ALL channel APIs
async function handleIncomingMessage(platformMessage, tenantId, leadId) {
  const messageId = extractMessageId(platformMessage);
  const channel = 'whatsapp'; // or 'discord', 'telegram', 'email'
  
  // Check duplicate
  const exists = await db.query(`
    SELECT id FROM et_messages 
    WHERE channel = $1 AND lead_id = $2 AND message_id = $3
  `, [channel, leadId, messageId]);
  
  if (exists) {
    console.log('Duplicate message, skipping');
    return;
  }
  
  // Insert message (trigger handles thread_id)
  await db.query(`
    INSERT INTO et_messages (
      tenant_id, lead_id, channel, message_id, timestamp,
      direction, message_type, text_content, raw_json
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
  `, [
    tenantId,
    leadId,
    channel,
    messageId,
    platformMessage.timestamp * 1000,
    'inbound',
    detectMessageType(platformMessage),
    extractTextContent(platformMessage),
    JSON.stringify(platformMessage)
  ]);
}
```

No thread logic. Simple insert.

### Required: Send Message (Outbound)

```javascript
// POST /send endpoint
async function sendMessage(req, res) {
  const { lead_id, message_type, text_content, media_url } = req.body;
  
  // Send via platform API
  const platformMessageId = await whatsappAPI.send({
    to: getLeadPhoneNumber(lead_id),
    type: message_type,
    text: text_content,
    media: media_url
  });
  
  // Record in database (trigger handles thread_id)
  await db.query(`
    INSERT INTO et_messages (
      tenant_id, lead_id, channel, message_id, timestamp,
      direction, message_type, text_content, raw_json
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
  `, [
    tenantId,
    lead_id,
    'whatsapp',
    platformMessageId,
    Date.now(),
    'outbound',
    message_type,
    text_content,
    JSON.stringify({ sent: true })
  ]);
  
  res.json({ success: true, message_id: platformMessageId });
}
```

### Required: Health Check

```javascript
// GET /health
{
  "status": "ok",
  "database": "connected",
  "platform": "connected"
}
```

---

## Field Mapping Reference

All Channel APIs must normalize platform-specific data:

| Our Schema | WhatsApp (Baileys) | Discord | Telegram | Email |
|------------|-------------------|---------|----------|-------|
| channel | "whatsapp" | "discord" | "telegram" | "email" |
| message_id | message.key.id | message.id | update.message.message_id | Message-ID header |
| timestamp | messageTimestamp * 1000 | timestamp * 1000 | date * 1000 | Date header to Unix ms |
| text_content | message.conversation | message.content | message.text | Email body (plain) |
| message_type | text/image/video/audio/document | text/image/video/file | text/photo/video/voice | text/html |
| raw_json | Full Baileys message | Full Discord message | Full Telegram update | Full MIME message |

---

## Deployment Configuration

Each Channel API Server on Railway:

```env
# Database (Shared)
DATABASE_URL=postgresql://user:password@db:5432/chatbot_db

# Channel-specific credentials
WHATSAPP_SESSION_DIR=/app/sessions        # Baileys
DISCORD_BOT_TOKEN=xxxxx                   # Discord
TELEGRAM_BOT_TOKEN=xxxxx                  # Telegram
SMTP_HOST=smtp.gmail.com                  # Email
SMTP_PORT=587

# Service config
PORT=3000
NODE_ENV=production
LOG_LEVEL=info
```

---

## Query Patterns

### Get Conversation History (for RAG)

```sql
-- All messages in a thread (chronological)
SELECT *
FROM et_messages
WHERE thread_id = 123
ORDER BY timestamp ASC;
```

### Get All Messages for Lead

```sql
-- Across all channels and threads
SELECT m.*, t.channel, t.status
FROM et_messages m
JOIN et_threads t ON m.thread_id = t.id
WHERE m.lead_id = 5001
ORDER BY m.timestamp ASC;
```

### Get Pending Outbound Messages

```sql
-- For Outbound Router to process
SELECT *
FROM et_messages
WHERE direction = 'outbound'
  AND raw_json->>'sent' IS NULL
ORDER BY created_at ASC;
```

---

## Implementation Phases

### Phase 1: WhatsApp (Baileys)
Status: Current
Server: Baileys API (Node.js)
Database: et_threads + et_messages
Features: Text, image, video, audio, document

### Phase 2: Discord
Status: Future
Server: Discord API (Node.js with discord.js)
Database: Same et_threads + et_messages
Features: Text, embeds, files

### Phase 3: Telegram
Status: Future
Server: Telegram API (Node.js with node-telegram-bot-api)
Database: Same et_threads + et_messages
Features: Text, photos, videos, voice, documents

### Phase 4: Email
Status: Future
Server: Email API (Node.js with nodemailer + IMAP)
Database: Same et_threads + et_messages
Features: Text, HTML, attachments

---

## Key Design Principles

1. UNIFIED SCHEMA: All channels use identical tables (et_threads, et_messages)
2. SIMPLE CHANNEL APIs: No complex logic, just insert messages
3. CENTRALIZED THREAD MANAGEMENT: PostgreSQL trigger handles thread creation/assignment
4. BIDIRECTIONAL: Same table for inbound and outbound (direction column)
5. IDEMPOTENT: Duplicate detection via (channel, lead_id, message_id)
6. EXTENSIBLE: Adding new channel = copy pattern, change platform API calls

---

## Success Criteria

Channel API is production-ready when:
- Receives platform messages → writes to et_messages
- Duplicate messages handled (no crashes, no duplicates in DB)
- Exposes POST /send for outbound messages
- Health check endpoint returns correct status
- All message types supported (text minimum, media recommended)
- Logging structured JSON to stdout
- No manual thread_id management needed

---

## Summary for Channel API Teams

YOU ONLY NEED TO:
1. Connect to shared PostgreSQL via DATABASE_URL
2. On incoming message:
   - Check if message_id already exists
   - If exists: skip
   - If new: INSERT into et_messages (direction='inbound')
3. Expose POST /send endpoint for outbound
4. Don't worry about thread_id - trigger handles it

THAT'S IT. Keep it simple.

---

End of Document
Version: 2.0
Last Updated: 2026-02-18
