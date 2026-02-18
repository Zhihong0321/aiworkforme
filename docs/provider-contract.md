# Provider Contract: UniAPI + Gemini 3 Flash Preview

This document defines the interface between the Eternalgy backend and the UniAPI.io provider for Google Gemini models.

## 1. Provider Configuration
- **Base URL**: `https://api.uniapi.io`
- **Primary Model**: `gemini-2.5-flash` (Targeting Gemini 3 Flash Preview capabilities)
- **Authentication**: Header-based via `x-goog-api-key`

## 2. Request Schema (Standard Chat)
`POST /gemini/v1beta/models/gemini-2.5-flash:generateContent`

```json
{
  "contents": [
    {
      "role": "user | model",
      "parts": [
        { "text": "string content" },
        { "inline_data": { "mime_type": "string", "data": "base64" } }
      ]
    }
  ],
  "system_instruction": {
    "parts": { "text": "System instructions here" }
  },
  "generationConfig": {
    "temperature": 0.7,
    "maxOutputTokens": 2048,
    "responseMimeType": "text/plain | application/json",
    "responseSchema": {}
  },
  "tools": [
    { "functionDeclarations": [] }
  ],
  "tool_config": {
    "function_calling_config": { "mode": "AUTO" }
  }
}
```

## 3. Response Schema
```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          { "text": "string" },
          { "functionCall": { "name": "string", "args": {} } }
        ],
        "role": "model"
      },
      "finishReason": "STOP | MAX_TOKENS | SAFETY | OTHER",
      "safetyRatings": []
    }
  ],
  "usageMetadata": {
    "promptTokenCount": "number",
    "candidatesTokenCount": "number",
    "totalTokenCount": "number"
  }
}
```

## 4. Error Model
| HTTP Status | Code | Message | Action |
| --- | --- | --- | --- |
| 400 | INVALID_ARGUMENT | Request body malformed | Log and alert |
| 401 | UNAUTHENTICATED | API key missing/invalid | Fatal |
| 429 | RESOURCE_EXHAUSTED | Rate limit hit | Retry with backoff |
| 500 | INTERNAL | Provider error | Retry once, then fail-fast |

## 5. Budget Tier Mapping (Planned)
- **GREEN**: `gemini-2.5-flash`, full context, multiple tool calls.
- **YELLOW**: `gemini-2.5-flash`, truncated context, limited tool calls.
- **RED**: `gemini-2.5-flash`, compact system prompt, no tools, max 512 output tokens.
