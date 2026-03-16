"""
Shared WhatsApp voice-note runtime for TTS generation, conversion, upload, send, and verification.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

import httpx
import requests
from fastapi import HTTPException
from sqlmodel import Session

from src.adapters.db.channel_models import ChannelSession
from src.adapters.db.crm_models import Lead
from src.adapters.db.tenant_models import SystemSetting

from .messaging_helpers import (
    extract_whatsapp_recipient as _extract_whatsapp_recipient,
    provider_headers as _provider_headers,
    resolve_whatsapp_base_url as _resolve_whatsapp_base_url,
    whatsapp_provider_session_identifier as _whatsapp_provider_session_identifier,
)

DEFAULT_TTS_MODEL = "qwen3-tts-flash"
DEFAULT_TTS_VOICE = "kiki"
DEFAULT_TTS_MIMETYPE = "audio/ogg; codecs=opus"
DEFAULT_UPLOAD_PROVIDER = "auto"


def resolve_uniapi_key(session: Session) -> str:
    uniapi_setting = session.get(SystemSetting, "uniapi_key")
    key = (
        (uniapi_setting.value if uniapi_setting and uniapi_setting.value else "")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("UNIAPI_API_KEY")
    )
    if not key:
        raise HTTPException(
            status_code=400,
            detail="UniAPI key is missing. Set /api/v1/settings/uniapi-key or OPENAI_API_KEY.",
        )
    return key


def resolve_ffmpeg_executable() -> str:
    if os.getenv("FFMPEG_BIN"):
        return os.environ["FFMPEG_BIN"]

    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail="No ffmpeg binary available. Install ffmpeg or imageio-ffmpeg for voice-note sends.",
        ) from exc


def generate_tts_audio(
    *,
    uniapi_key: str,
    text_content: str,
    model: str,
    voice: str,
    instructions: Optional[str],
    timeout_seconds: float = 60.0,
) -> Tuple[bytes, str]:
    uniapi_base = (os.getenv("UNIAPI_OPENAI_BASE_URL") or "https://api.uniapi.io/v1").rstrip("/")
    payload: Dict[str, Any] = {
        "model": (model or "").strip() or DEFAULT_TTS_MODEL,
        "voice": (voice or "").strip() or DEFAULT_TTS_VOICE,
        "input": text_content,
    }
    if instructions and str(instructions).strip():
        payload["instructions"] = str(instructions).strip()

    try:
        response = requests.post(
            f"{uniapi_base}/audio/speech",
            headers={
                "Authorization": f"Bearer {uniapi_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TTS request failed: {str(exc)}") from exc

    if response.status_code >= 400:
        detail = response.text[:400]
        raise HTTPException(status_code=502, detail=f"TTS failed ({response.status_code}): {detail}")

    body = response.content or b""
    if not body:
        raise HTTPException(status_code=502, detail="TTS returned empty audio content")
    content_type = (response.headers.get("content-type") or "audio/wav").split(";")[0].strip() or "audio/wav"
    return body, content_type


def convert_audio_to_voice_note(audio_bytes: bytes, input_content_type: str) -> Tuple[bytes, str, Optional[str]]:
    lowered = str(input_content_type or "").lower()
    if "ogg" in lowered and "opus" in lowered:
        return audio_bytes, DEFAULT_TTS_MIMETYPE, None

    ffmpeg_bin = resolve_ffmpeg_executable()
    input_suffix = ".wav" if "wav" in lowered else ".audio"

    with tempfile.NamedTemporaryFile(suffix=input_suffix, delete=False) as source_file:
        source_file.write(audio_bytes)
        source_path = Path(source_file.name)

    output_path = source_path.with_suffix(source_path.suffix + ".ogg")
    try:
        command = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(source_path),
            "-c:a",
            "libopus",
            "-b:a",
            "24k",
            "-vbr",
            "on",
            "-application",
            "voip",
            str(output_path),
        ]
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        if process.returncode != 0 or not output_path.exists():
            raise HTTPException(
                status_code=502,
                detail="ffmpeg conversion to WhatsApp voice-note format failed",
            )
        return output_path.read_bytes(), DEFAULT_TTS_MIMETYPE, "transcoded_to_ogg_opus"
    finally:
        try:
            source_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            output_path.unlink(missing_ok=True)
        except Exception:
            pass


def upload_to_catbox(file_name: str, audio_bytes: bytes, timeout_seconds: float) -> str:
    response = requests.post(
        "https://catbox.moe/user/api.php",
        data={"reqtype": "fileupload"},
        files={"fileToUpload": (file_name, audio_bytes, "audio/ogg")},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    public_url = response.text.strip()
    if not public_url.startswith("http"):
        raise RuntimeError(f"Unexpected Catbox response: {public_url}")
    return public_url


def upload_to_tmpfiles(file_name: str, audio_bytes: bytes, timeout_seconds: float) -> str:
    response = requests.post(
        "https://tmpfiles.org/api/v1/upload",
        files={"file": (file_name, audio_bytes, "audio/ogg")},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    public_url = (((payload.get("data") or {}).get("url")) or "").strip()
    if not public_url.startswith("http"):
        raise RuntimeError(f"Unexpected tmpfiles response: {payload}")
    if public_url.startswith("http://tmpfiles.org/"):
        public_url = public_url.replace("http://tmpfiles.org/", "https://tmpfiles.org/dl/", 1)
    return public_url


def upload_voice_note_bytes(
    audio_bytes: bytes,
    *,
    provider: Optional[str] = None,
    timeout_seconds: float = 120.0,
) -> Tuple[str, str]:
    chosen = (provider or os.getenv("WHATSAPP_VOICE_UPLOAD_PROVIDER") or DEFAULT_UPLOAD_PROVIDER).strip().lower()
    providers = ("catbox", "tmpfiles") if chosen in {"", "auto"} else (chosen,)
    last_error: Optional[str] = None

    for current in providers:
        try:
            if current == "catbox":
                return upload_to_catbox("voice-note.ogg", audio_bytes, timeout_seconds), "catbox"
            if current == "tmpfiles":
                return upload_to_tmpfiles("voice-note.ogg", audio_bytes, timeout_seconds), "tmpfiles"
        except Exception as exc:
            last_error = f"{current}: {exc}"

    raise HTTPException(
        status_code=502,
        detail=f"Voice-note upload failed. Last error: {last_error}",
    )


def send_whatsapp_voice_note(
    *,
    channel_session: ChannelSession,
    lead: Lead,
    audio_url: str,
    mimetype: str = DEFAULT_TTS_MIMETYPE,
    timeout_seconds: float = 45.0,
) -> Dict[str, Any]:
    base_url = _resolve_whatsapp_base_url(channel_session)
    send_url = f"{base_url}/messages/send"
    payload = {
        "sessionId": _whatsapp_provider_session_identifier(channel_session),
        "to": _extract_whatsapp_recipient(lead.external_id),
        "audioUrl": audio_url,
        "mimetype": mimetype or DEFAULT_TTS_MIMETYPE,
        "ptt": True,
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(send_url, headers=_provider_headers(), json=payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Voice note send failed: {str(exc)}") from exc

    body: Dict[str, Any] = {}
    if response.content:
        try:
            body = response.json()
        except Exception:
            body = {"raw": response.text[:400]}

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Voice note send failed ({response.status_code}): {str(body)[:400]}",
        )

    result = body.get("result") if isinstance(body, dict) else {}
    key = result.get("key") if isinstance(result, dict) else {}
    provider_message_id = (
        (body.get("provider_message_id") if isinstance(body, dict) else None)
        or (body.get("message_id") if isinstance(body, dict) else None)
        or (key.get("id") if isinstance(key, dict) else None)
    )
    remote_jid = key.get("remoteJid") if isinstance(key, dict) else None
    status_text = str(body.get("status") if isinstance(body, dict) else "").strip().lower()
    if status_text != "sent" or not provider_message_id:
        raise HTTPException(
            status_code=502,
            detail=f"Voice note send returned non-sent status: {str(body)[:400]}",
        )

    return {
        "provider_message_id": str(provider_message_id),
        "remote_jid": str(remote_jid) if remote_jid else None,
        "provider_status": status_text or None,
        "send_variant_used": "audio_url_ptt",
        "send_attempts": [{"variant": "audio_url_ptt", "status_code": response.status_code}],
        "provider_response": body,
    }


def verify_whatsapp_message_visible(
    *,
    channel_session: ChannelSession,
    remote_jid: str,
    provider_message_id: str,
    timeout_seconds: float = 20.0,
    max_polls: int = 3,
) -> None:
    if not remote_jid or not provider_message_id:
        return

    base_url = _resolve_whatsapp_base_url(channel_session)
    verify_url = f"{base_url}/chats/{quote(remote_jid, safe='')}/messages"
    verify_error: Optional[str] = None

    with httpx.Client(timeout=timeout_seconds) as client:
        for _ in range(max_polls):
            try:
                response = client.get(
                    verify_url,
                    headers=_provider_headers(),
                    params={
                        "sessionId": _whatsapp_provider_session_identifier(channel_session),
                        "limit": 30,
                    },
                )
                if response.status_code < 400:
                    payload = response.json() if response.content else {}
                    messages = []
                    if isinstance(payload, dict):
                        if isinstance(payload.get("messages"), list):
                            messages = payload.get("messages") or []
                        elif isinstance(payload.get("result"), list):
                            messages = payload.get("result") or []
                        elif isinstance(payload.get("result"), dict) and isinstance(payload["result"].get("messages"), list):
                            messages = payload["result"].get("messages") or []

                    for message in messages:
                        if not isinstance(message, dict):
                            continue
                        key = message.get("key") if isinstance(message.get("key"), dict) else {}
                        current_id = key.get("id") or message.get("id") or message.get("messageId")
                        if str(current_id or "") == provider_message_id:
                            return
            except Exception as exc:
                verify_error = str(exc)
            time.sleep(1.0)

    raise HTTPException(
        status_code=502,
        detail=(
            "Provider returned sent but message was not found in recent chat history. "
            f"message_id={provider_message_id}"
            + (f", verify_error={verify_error}" if verify_error else "")
        ),
    )


def dispatch_generated_voice_note(
    *,
    session: Session,
    channel_session: ChannelSession,
    lead: Lead,
    text_content: str,
    model: Optional[str] = None,
    voice: Optional[str] = None,
    instructions: Optional[str] = None,
    timeout_seconds: float = 60.0,
) -> Dict[str, Any]:
    requested_text = (text_content or "").strip()
    if not requested_text:
        raise HTTPException(status_code=400, detail="text_content is required")

    model_name = (model or "").strip() or DEFAULT_TTS_MODEL
    voice_name = (voice or "").strip() or DEFAULT_TTS_VOICE
    instructions_text = (instructions or "").strip() or None

    raw_audio_bytes, raw_content_type = generate_tts_audio(
        uniapi_key=resolve_uniapi_key(session),
        text_content=requested_text,
        model=model_name,
        voice=voice_name,
        instructions=instructions_text,
        timeout_seconds=timeout_seconds,
    )
    voice_audio_bytes, voice_content_type, transcode_note = convert_audio_to_voice_note(
        raw_audio_bytes,
        raw_content_type,
    )
    public_audio_url, upload_provider = upload_voice_note_bytes(
        voice_audio_bytes,
        timeout_seconds=max(timeout_seconds, 120.0),
    )
    send_result = send_whatsapp_voice_note(
        channel_session=channel_session,
        lead=lead,
        audio_url=public_audio_url,
        mimetype=voice_content_type,
        timeout_seconds=max(timeout_seconds, 45.0),
    )
    verify_whatsapp_message_visible(
        channel_session=channel_session,
        remote_jid=str(send_result.get("remote_jid") or ""),
        provider_message_id=str(send_result.get("provider_message_id") or ""),
    )

    return {
        "tts_model": model_name,
        "tts_voice": voice_name,
        "tts_requested_text": requested_text,
        "tts_text_used": requested_text,
        "tts_content_type": voice_content_type,
        "tts_audio_bytes": len(voice_audio_bytes),
        "tts_transcode_note": transcode_note,
        "temp_media_url": public_audio_url,
        "upload_provider": upload_provider,
        **send_result,
    }
