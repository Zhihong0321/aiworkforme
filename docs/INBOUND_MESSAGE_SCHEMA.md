# Message Schema - ALL Messages (Inbound + Outbound)

## Table: et_messages

All messages (inbound from customers, outbound from AI) in ONE table. Easy to query conversation history.

```sql
CREATE TABLE et_messages (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    
    -- Channel info
    channel_type VARCHAR(50) NOT NULL,
    channel_session_id VARCHAR(255) NOT NULL,
    
    -- Message identity
    channel_message_id VARCHAR(255) NOT NULL,
    channel_timestamp BIGINT NOT NULL,
    
    -- Direction and participants
    direction VARCHAR(20) NOT NULL,
    sender_id VARCHAR(255) NOT NULL,
    recipient_id VARCHAR(255) NOT NULL,
    
    -- Content
    message_type VARCHAR(50) NOT NULL DEFAULT 'text',
    text_content TEXT,
    media_url TEXT,
    raw_json JSONB NOT NULL,
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    UNIQUE(channel_type, channel_session_id, channel_message_id)
);

CREATE INDEX idx_msg_tenant ON et_messages(tenant_id);
CREATE INDEX idx_msg_conversation ON et_messages(channel_session_id, sender_id, recipient_id, channel_timestamp);
CREATE INDEX idx_msg_created ON et_messages(created_at DESC);
```

## Column Explanations

### tenant_id
Your company ID (we configure this)

### channel_type
"whatsapp", "email", "discord", "telegram"

### channel_session_id
Your business WhatsApp number: "+60123456789"

### channel_message_id
Unique message ID from platform (prevents duplicates)

### channel_timestamp
When message was sent (Unix milliseconds)

### direction
- "inbound" = Customer sent to you
- "outbound" = You/AI sent to customer

### sender_id
**Inbound:** Customer WhatsApp "+60111222333"
**Outbound:** Your WhatsApp "+60123456789"

### recipient_id
**Inbound:** Your WhatsApp "+60123456789"  
**Outbound:** Customer WhatsApp "+60111222333"

### message_type
"text", "image", "video", "audio", "document"

### text_content
Message text or caption (NULL for media without caption)

### media_url
URL to media file (NULL if no media)

### raw_json
Full original message object from WhatsApp

### created_at
When we stored it in database

## Example Records

**Customer sends "Hello":**
```sql
INSERT INTO et_messages VALUES (
    101,                    -- tenant_id
    'whatsapp',             -- channel_type
    '+60123456789',         -- channel_session_id (YOUR WhatsApp)
    '3EB0ABC123',           -- channel_message_id
    1708186800000,          -- channel_timestamp
    'inbound',              -- direction
    '+60111222333',         -- sender_id (CUSTOMER)
    '+60123456789',         -- recipient_id (YOU)
    'text',                 -- message_type
    'Hello',                -- text_content
    NULL,                   -- media_url
    '{...}'                 -- raw_json
);
```

**AI replies "Hi, how can I help?":**
```sql
INSERT INTO et_messages VALUES (
    101,                    -- tenant_id
    'whatsapp',             -- channel_type
    '+60123456789',         -- channel_session_id (YOUR WhatsApp)
    '3EB0XYZ789',           -- channel_message_id
    1708186820000,          -- channel_timestamp
    'outbound',             -- direction
    '+60123456789',         -- sender_id (YOU)
    '+60111222333',         -- recipient_id (CUSTOMER)
    'text',                 -- message_type
    'Hi, how can I help?',  -- text_content
    NULL,                   -- media_url
    '{...}'                 -- raw_json
);
```

## Query Conversation History (for RAG)

```sql
-- Get all messages between your WhatsApp and a customer
SELECT *
FROM et_messages
WHERE channel_session_id = '+60123456789'  -- Your WhatsApp
  AND (
    (direction = 'inbound' AND sender_id = '+60111222333')
    OR (direction = 'outbound' AND recipient_id = '+60111222333')
  )
ORDER BY channel_timestamp ASC;
```

This returns chronological conversation for your AI to analyze.

## Simple, right?
