import json
import re
from typing import Optional

from mcp.server.fastmcp import FastMCP


app = FastMCP("voice_note_followup")

ALLOWED_TRIGGER_REASONS = {
    "appointment_request",
    "cold_followup",
    "no_response_push",
    "soft_rejection_recovery",
    "feedback_probe",
}
DEFAULT_VOICE = "kiki"
DEFAULT_MODEL = "qwen3-tts-flash"
MAX_SECONDS_HARD_CAP = 15


def _normalize_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text.replace("\n", " ").replace("\r", " ").strip()


def _contains_cjk(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x4E00 <= codepoint <= 0x9FFF
        or 0x3400 <= codepoint <= 0x4DBF
        or 0x3040 <= codepoint <= 0x30FF
        or 0xAC00 <= codepoint <= 0xD7AF
    )


def _estimate_duration_seconds(text: str) -> float:
    cjk_chars = sum(1 for char in text if _contains_cjk(char))
    latin_words = len(re.findall(r"[A-Za-z0-9']+", text))
    punctuation = len(re.findall(r"[,.!?;:，。！？；：]", text))
    seconds = (cjk_chars * 0.32) + (latin_words * 0.42) + (punctuation * 0.08)
    if seconds <= 0:
        seconds = 1.5
    return round(seconds, 1)


@app.tool()
async def request_voice_note_followup(
    spoken_text: str,
    trigger_reason: str,
    customer_signal: Optional[str] = None,
    max_seconds: int = MAX_SECONDS_HARD_CAP,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Validate and prepare a short WhatsApp voice-note follow-up request.
    Use only for stronger emotional persuasion after weak customer engagement,
    soft rejection, or repeated failed text/image follow-ups.
    """
    normalized_text = _normalize_text(spoken_text)
    normalized_reason = _normalize_text(trigger_reason).lower().replace(" ", "_")
    seconds_cap = min(int(max_seconds or MAX_SECONDS_HARD_CAP), MAX_SECONDS_HARD_CAP)
    estimated_seconds = _estimate_duration_seconds(normalized_text)
    sentence_parts = [part for part in re.split(r"[.!?。！？]+", normalized_text) if part.strip()]

    approved = True
    issues = []

    if not normalized_text:
        approved = False
        issues.append("spoken_text is required")
    if normalized_reason not in ALLOWED_TRIGGER_REASONS:
        approved = False
        issues.append(
            "trigger_reason must be one of: " + ", ".join(sorted(ALLOWED_TRIGGER_REASONS))
        )
    if len(sentence_parts) > 2:
        approved = False
        issues.append("voice note must be 1-2 short sentences only")
    if estimated_seconds > seconds_cap:
        approved = False
        issues.append(
            f"estimated duration {estimated_seconds}s exceeds hard cap of {seconds_cap}s"
        )

    result = {
        "approved": approved,
        "message_type": "audio",
        "spoken_text": normalized_text,
        "trigger_reason": normalized_reason,
        "customer_signal": _normalize_text(customer_signal or ""),
        "estimated_duration_seconds": estimated_seconds,
        "max_seconds": seconds_cap,
        "tts_model": _normalize_text(model) or DEFAULT_MODEL,
        "tts_voice": _normalize_text(voice) or DEFAULT_VOICE,
        "tts_instructions": (
            "Speak like a sincere human WhatsApp voice note. "
            "Warm, emotionally honest, persuasive, and concise."
        ),
        "issues": issues,
        "cost_guard": "voice_note_cost_is_high_use_only_for_strong_follow_up_cases",
    }
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    app.run()
