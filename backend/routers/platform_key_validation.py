"""
MODULE: Platform API Key Validation Helpers
PURPOSE: Shared key masking/provider metadata and provider key validation calls.
DOES: Keep provider-specific validation logic isolated from route handlers.
DOES NOT: Access DB session or mutate system settings.
INVARIANTS: Validation result tuple format remains (is_valid, detail).
SAFE CHANGE: Add new providers by extending metadata + validator.
"""

import httpx
from fastapi import HTTPException, status

from .platform_schemas import PROVIDER_SETTINGS


def mask_secret(value: str, head: int, tail: int) -> str:
    if not value:
        return ""
    if len(value) <= head + tail:
        return "***"
    return f"{value[:head]}...{value[-tail:]}"


def provider_meta(provider: str) -> tuple[str, int, int]:
    normalized = provider.strip().lower()
    meta = PROVIDER_SETTINGS.get(normalized)
    if not meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported provider")
    return meta


def validate_zai_key(api_key: str) -> tuple[bool, str]:
    url = "https://api.z.ai/api/coding/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "glm-4.7-flash",
        "messages": [{"role": "user", "content": "ping"}],
        "temperature": 0,
        "max_tokens": 1,
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                detail = resp.text[:240] if resp.text else f"HTTP {resp.status_code}"
                return False, f"Z.ai validation failed: {detail}"
            body = resp.json() if resp.content else {}
            choices = body.get("choices") if isinstance(body, dict) else None
            if not choices:
                return False, "Z.ai key check returned no choices"
            return True, "Z.ai key is valid"
    except Exception as exc:
        return False, f"Z.ai validation error: {str(exc)}"


def validate_uniapi_key(api_key: str) -> tuple[bool, str]:
    url = "https://api.uniapi.io/gemini/v1beta/models/gemini-3-flash-preview:generateContent"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "ping"}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 1},
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                detail = resp.text[:240] if resp.text else f"HTTP {resp.status_code}"
                return False, f"UniAPI validation failed: {detail}"
            body = resp.json() if resp.content else {}
            candidates = body.get("candidates") if isinstance(body, dict) else None
            if not candidates:
                return False, "UniAPI key check returned no candidates"
            return True, "UniAPI key is valid"
    except Exception as exc:
        return False, f"UniAPI validation error: {str(exc)}"
