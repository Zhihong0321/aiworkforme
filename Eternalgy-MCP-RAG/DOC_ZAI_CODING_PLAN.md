# Z.ai Coding Plan API Integration Guide

## Overview
This project connects to Z.ai's **Coding Plan Endpoint**, which differs from the standard paid API. This endpoint is designed for coding and reasoning tasks and offers zero-balance access for specific models.

## Critical Configuration

### 1. Base URL
You **MUST** use the following Base URL. Do not use the general Z.ai API URL.
```python
BASE_URL = "https://api.z.ai/api/coding/paas/v4"
```

### 2. Authentication
*   **API Key**: Required.
*   **Source**: Environment variable `ZAI_API_KEY`.
*   **Header**: Standard Bearer Token authorization.

### 3. Supported Models
The Coding Plan endpoint primarily supports the GLM-4 series:
*   `glm-4.6`
*   `glm-4.5`
*   `glm-4.5-air`
*   `glm-4.5-flash`
*   `glm-4.5V` (Vision)

## Implementation Details

### Client Initialization (Critical: Timeouts)
The Coding Plan endpoint can have long response times due to "Chain of Thought" generation. You **MUST** configure a custom HTTP client with extended timeouts (e.g., 300s) and connection pooling.

**Recommended Pattern (`backend/app/core/zai_client.py`):**
```python
from openai import OpenAI
import httpx
import os

# Create a custom HTTP client for better performance and stability
http_client = httpx.Client(
    timeout=300.0,  # 5 minutes timeout to handle long reasoning chains
    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
)

client = OpenAI(
    api_key=os.getenv("ZAI_API_KEY"),
    base_url="https://api.z.ai/api/coding/paas/v4",
    http_client=http_client
)
```

### Handling Responses: Reasoning vs Content
The Coding Plan endpoint often returns the model's "Chain of Thought" in a special field called `reasoning_content`. Sometimes the standard `content` field is empty.

**Production Logic:**
The system should prioritize `content`, but strictly fallback to `reasoning_content` if `content` is missing.

```python
response = client.chat.completions.create(
    model="glm-4.6",
    messages=[...],
    temperature=0.7,
    max_tokens=2000
)

message = response.choices[0].message
content = message.content

# Fallback: If content is empty but reasoning exists, treat reasoning as the content
if not content and message.reasoning_content:
    content = message.reasoning_content

final_result = {
    "content": content,
    "reasoning_content": message.reasoning_content
}
```

### Advanced Features

#### Tool Calling (MCP Support)
The Coding Plan endpoint fully supports the OpenAI-compatible `tools` and `tool_choice` parameters. This is essential for the MCP (Model Context Protocol) integration.
*   **Format**: Standard OpenAI Tool format.
*   **Behavior**: The model generates `tool_calls` in the response message.

#### Streaming
Streaming is supported (`stream=True`).
*   **Reasoning**: If the model streams reasoning, it may arrive in `delta.reasoning_content` (verify SDK support, otherwise it appears in standard chunks).

### Error Handling
*   **HTTP 429**: Rate limit exceeded. (Code 1305 is also observed).
*   **Error 1113**: "Insufficient Balance". This usually occurs if you accidentally access the *paid* endpoint (`https://api.z.ai/api/paas/v4`) instead of the coding endpoint. **Fix:** Verify your `base_url`.
*   **Connection Timeouts**: Handled by the `httpx` client configuration.

## Summary
*   **Target**: Z.ai Coding PaaS v4
*   **Advantage**: Monthly subscription/Free tier (Plan dependent) vs Token usage.
*   **Requirement 1**: Handle `reasoning_content` field (Fallback logic).
*   **Requirement 2**: Use `httpx` with 300s timeout.
*   **Capability**: Supports Function Calling (Tools) and Streaming.
