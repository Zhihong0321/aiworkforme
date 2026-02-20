"""
MODULE: Messaging Payload Helpers
PURPOSE: Provider payload parsing/normalization helpers for messaging routes.
DOES: Extract message/chat identifiers and normalize timestamp/text/type values.
DOES NOT: Perform DB access or tenant/session validation.
INVARIANTS: Parsed values remain backward-compatible for existing import/dispatch flows.
SAFE CHANGE: Keep extraction fallback order stable.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional


def normalize_usage(usage: Dict[str, Any]) -> Dict[str, Any]:
    usage = usage or {}
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", 0) or 0)
    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "raw_usage": usage.get("raw_usage", usage),
    }


def extract_list(body: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    if isinstance(body.get(key), list):
        return [item for item in body.get(key, []) if isinstance(item, dict)]
    if isinstance(body.get("result"), dict) and isinstance(body["result"].get(key), list):
        return [item for item in body["result"].get(key, []) if isinstance(item, dict)]
    if key == "chats" and isinstance(body.get("result"), list):
        return [item for item in body.get("result", []) if isinstance(item, dict)]
    if key == "messages" and isinstance(body.get("result"), list):
        return [item for item in body.get("result", []) if isinstance(item, dict)]
    if isinstance(body.get("data"), list):
        return [item for item in body.get("data", []) if isinstance(item, dict)]
    return []


def chat_jid(chat: Dict[str, Any]) -> Optional[str]:
    raw_id = chat.get("id") or chat.get("jid") or chat.get("chatId")
    if isinstance(raw_id, dict):
        raw_id = raw_id.get("_serialized") or raw_id.get("id") or raw_id.get("jid")
    if raw_id is None:
        return None
    value = str(raw_id).strip()
    return value or None


def chat_display_name(chat: Dict[str, Any], fallback_jid: str) -> str:
    for key in ("name", "subject", "notify", "pushName", "formattedName"):
        value = chat.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback_jid


def name_confidence_score(name: Optional[str], external_id: Optional[str], jid: Optional[str]) -> int:
    value = (name or "").strip()
    if not value:
        return 0
    lowered = value.lower()
    if lowered in {"unknown", "null", "none", "n/a", "whatsapp"}:
        return 0
    digits_only = re.sub(r"\D+", "", value)
    if len(digits_only) >= 8 and len(digits_only) >= max(1, len(value) - 2):
        return 0

    score = 1
    if " " in value:
        score += 1
    if re.search(r"[a-zA-Z]", value):
        score += 1
    if len(value) >= 4:
        score += 1

    candidate_tokens = {
        (external_id or "").strip().lower(),
        (jid or "").strip().lower(),
        ((jid or "").split("@", 1)[0] if jid else "").strip().lower(),
        digits_only.strip().lower(),
    }
    if lowered in candidate_tokens:
        score = 0
    return score


def normalize_whatsapp_external_id_from_jid(jid: str) -> Optional[str]:
    if not jid:
        return None
    left = jid.split("@", 1)[0]
    digits = re.sub(r"\D+", "", left)
    if 8 <= len(digits) <= 15:
        return digits
    normalized = left.strip()
    return normalized or None


def chat_phone_number(chat: Dict[str, Any]) -> Optional[str]:
    phone = chat.get("phoneNumber")
    if not isinstance(phone, str):
        return None
    digits = re.sub(r"\D+", "", phone)
    if not digits:
        return None
    return digits


def normalize_seed_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = re.sub(r"\D+", "", str(phone))
    if not digits:
        return None
    return digits


def phone_match_keys(value: Optional[str]) -> List[str]:
    if not value:
        return []
    raw = str(value).strip()
    digits = re.sub(r"\D+", "", raw)
    keys: List[str] = []
    seen: set[str] = set()

    def add(key: Optional[str]):
        if not key:
            return
        k = key.strip()
        if not k or k in seen:
            return
        seen.add(k)
        keys.append(k)

    add(raw)
    add(digits)
    if digits.startswith("0") and len(digits) >= 9:
        add("6" + digits)
    if digits.startswith("60") and len(digits) >= 10:
        add("0" + digits[2:])
    return keys


def to_datetime(value: Any) -> datetime:
    if value is None:
        return datetime.utcnow()
    try:
        ts = float(value)
        if ts > 1_000_000_000_000:
            ts = ts / 1000.0
        if ts < 0:
            return datetime.utcnow()
        return datetime.utcfromtimestamp(ts)
    except Exception:
        return datetime.utcnow()


def message_external_id(message: Dict[str, Any]) -> Optional[str]:
    key = message.get("key") if isinstance(message.get("key"), dict) else {}
    candidates = [
        key.get("id"),
        message.get("id"),
        message.get("messageId"),
        message.get("_id"),
    ]
    for raw in candidates:
        if raw is None:
            continue
        value = str(raw).strip()
        if value:
            return value
    return None


def message_direction(message: Dict[str, Any]) -> str:
    key = message.get("key") if isinstance(message.get("key"), dict) else {}
    from_me = message.get("fromMe")
    if from_me is None:
        from_me = key.get("fromMe")
    return "outbound" if bool(from_me) else "inbound"


def message_text(message: Dict[str, Any]) -> Optional[str]:
    if isinstance(message.get("content"), str) and message["content"].strip():
        return message["content"].strip()

    if isinstance(message.get("text"), str) and message["text"].strip():
        return message["text"].strip()

    body = message.get("message")
    if not isinstance(body, dict):
        return None

    if isinstance(body.get("conversation"), str) and body["conversation"].strip():
        return body["conversation"].strip()

    for msg_key in ("extendedTextMessage", "imageMessage", "videoMessage", "documentMessage"):
        container = body.get(msg_key)
        if isinstance(container, dict):
            for text_key in ("text", "caption"):
                text_val = container.get(text_key)
                if isinstance(text_val, str) and text_val.strip():
                    return text_val.strip()
    return None


def message_timestamp(message: Dict[str, Any]) -> datetime:
    ts = (
        message.get("messageTimestamp")
        or message.get("timestamp")
        or (message.get("key") or {}).get("timestamp")
    )
    return to_datetime(ts)


def message_type(message: Dict[str, Any]) -> str:
    raw_type = message.get("type")
    if isinstance(raw_type, str) and raw_type.strip():
        mapped = raw_type.strip().lower()
        if mapped in {"conversation", "extendedtextmessage"}:
            return "text"
        return mapped

    body = message.get("message")
    if isinstance(body, dict):
        if "conversation" in body or "extendedTextMessage" in body:
            return "text"
        if "imageMessage" in body:
            return "image"
        if "videoMessage" in body:
            return "video"
        if "audioMessage" in body:
            return "audio"
        if "documentMessage" in body:
            return "document"
        if "stickerMessage" in body:
            return "sticker"
        if "reactionMessage" in body:
            return "reaction"
    return "unknown"


def message_raw_payload(message: Dict[str, Any]) -> Dict[str, Any]:
    raw = message.get("raw")
    if isinstance(raw, dict):
        return raw
    return message
