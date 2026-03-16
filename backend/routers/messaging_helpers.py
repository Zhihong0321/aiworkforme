"""
MODULE: Messaging Helpers Facade
PURPOSE: Backward-compatible import facade for messaging helper functions.
DOES: Re-export validation and payload helper modules.
DOES NOT: Implement helper logic directly.
INVARIANTS: Existing import paths remain stable during refactor.
SAFE CHANGE: Remove facade only after all imports are migrated.
"""

import re
from typing import Any, Dict, Optional

from src.adapters.db.channel_models import ChannelSession

from .messaging_helpers_payload import *  # noqa: F401,F403
from .messaging_helpers_validation import *  # noqa: F401,F403


def _normalize_whatsapp_phone_candidate(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None

    if "@" in raw:
        raw = raw.split("@", 1)[0]

    digits = re.sub(r"\D+", "", raw)
    if 8 <= len(digits) <= 15:
        return digits
    return None


def _extract_whatsapp_phone_from_payload(payload: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(payload, dict):
        return None

    stack = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for value in current.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
                    continue
                if not isinstance(value, str):
                    continue
                candidate = _normalize_whatsapp_phone_candidate(value)
                if candidate and ("@s.whatsapp.net" in value or "@lid" in value or len(candidate) >= 8):
                    return candidate
            continue
        if isinstance(current, list):
            stack.extend(current)
    return None


def sync_whatsapp_channel_identity(
    channel_session: ChannelSession,
    *,
    provider_payload: Optional[Dict[str, Any]] = None,
    explicit_phone: Optional[str] = None,
    description: Optional[str] = None,
    provider_session_id: Optional[str] = None,
) -> bool:
    metadata = dict(channel_session.session_metadata or {})
    changed = False

    description_value = str(description or "").strip()
    if description_value and metadata.get("description") != description_value:
        metadata["description"] = description_value
        changed = True

    provider_session_value = str(
        provider_session_id or metadata.get("provider_session_id") or channel_session.session_identifier or ""
    ).strip()
    if provider_session_value and metadata.get("provider_session_id") != provider_session_value:
        metadata["provider_session_id"] = provider_session_value
        changed = True

    connected_number = _normalize_whatsapp_phone_candidate(explicit_phone) or _extract_whatsapp_phone_from_payload(
        provider_payload
    )
    if connected_number:
        for key in ("phone", "phone_number", "whatsapp_number", "wa_phone", "connected_number"):
            if metadata.get(key) != connected_number:
                metadata[key] = connected_number
                changed = True

        if metadata.get("channel_identity") != connected_number:
            metadata["channel_identity"] = connected_number
            changed = True

        if channel_session.session_identifier != connected_number:
            channel_session.session_identifier = connected_number
            changed = True

        if str(channel_session.display_name or "").strip() != connected_number:
            channel_session.display_name = connected_number
            changed = True

    if channel_session.session_metadata != metadata:
        channel_session.session_metadata = metadata
        changed = True

    return changed
