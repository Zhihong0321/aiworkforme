# Frontend Guide: Managing Z.ai API Key

## Overview
This feature allows administrators to manage the Z.ai API key dynamically from the Admin Dashboard, without needing to restart the backend or modify environment variables.

## Endpoints

### 1. Check Key Status
**GET** `/api/v1/settings/zai-key`

**Response (Key Exists):**
```json
{
  "status": "set",
  "masked_key": "********"
}
```

**Response (Key Missing):**
```json
{
  "status": "not_set",
  "masked_key": null
}
```

### 2. Update Key
**POST** `/api/v1/settings/zai-key`

**Body:**
```json
{
  "api_key": "your-new-zai-api-key-here"
}
```

**Response:**
```json
{
  "status": "updated"
}
```

## Implementation Instructions

1.  **UI Location**: Add a "Settings" or "System Config" section to the Admin Dashboard (`Dashboard.vue`).
2.  **Form**: Create a simple card with:
    *   **Title**: "Z.ai Connection"
    *   **Status Badge**: Green ("Connected") if `status === 'set'`, Red ("Missing") otherwise.
    *   **Input Field**: Password input (`type="password"`) for the API Key.
    *   **Save Button**: Triggers the POST request.
3.  **Behavior**:
    *   On mount, call `GET` to check status.
    *   If key is set, show the masked version in a read-only field or just "********".
    *   When user types a new key and clicks Save, call `POST`.
    *   Show a success toast notification: "System API Key Updated".
