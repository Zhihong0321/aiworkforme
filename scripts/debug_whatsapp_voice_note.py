#!/usr/bin/env python
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import requests


DEFAULT_UNIAPI_BASE = "https://api.uniapi.io/v1"
DEFAULT_BAILEYS_BASE = "https://ee-baileys-production.up.railway.app"
DEFAULT_MODEL = "qwen3-tts-flash"
DEFAULT_VOICE = "kiki"
DEFAULT_INPUT = "Hello, this is a WhatsApp voice note debug test from the IDE."
DEFAULT_INSTRUCTIONS = "Speak naturally and clearly, like a short voice note."
DEFAULT_MIMETYPE = "audio/ogg; codecs=opus"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a TTS sample, convert it to WhatsApp voice-note format, "
        "upload it to a public URL, then send it through the Baileys API.",
    )
    parser.add_argument("--uniapi-key", default=os.getenv("UNIAPI_KEY") or os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--uniapi-base", default=os.getenv("UNIAPI_OPENAI_BASE_URL") or DEFAULT_UNIAPI_BASE)
    parser.add_argument("--baileys-base", default=os.getenv("BAILEYS_BASE_URL") or DEFAULT_BAILEYS_BASE)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--to", required=True, help="Recipient digits or WhatsApp JID")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--instructions", default=DEFAULT_INSTRUCTIONS)
    parser.add_argument("--mimetype", default=DEFAULT_MIMETYPE)
    parser.add_argument(
        "--upload-provider",
        choices=("auto", "catbox", "tmpfiles"),
        default="auto",
        help="Public host used for the generated OGG file.",
    )
    parser.add_argument(
        "--public-audio-url",
        default="",
        help="Skip upload and send this already-public OGG/Opus URL directly.",
    )
    parser.add_argument(
        "--output-dir",
        default="test-results/voice-debug",
        help="Directory where raw and converted audio plus metadata will be stored.",
    )
    parser.add_argument(
        "--send-text-control",
        action="store_true",
        help="Send a plain text control message first to verify the session can send anything at all.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=12,
        help="How long to poll recent chat history for the sent voice-note message id.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="HTTP timeout for outbound API calls.",
    )
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def log(title: str, value: Any = "") -> None:
    if value == "":
        print(f"[debug] {title}")
    else:
        print(f"[debug] {title}: {value}")


def normalize_recipient(value: str) -> str:
    raw = str(value or "").strip()
    if "@s.whatsapp.net" in raw:
        return raw.split("@", 1)[0]
    return "".join(ch for ch in raw if ch.isdigit()) or raw


def get_session_status(base_url: str, session_id: str, timeout: int) -> Dict[str, Any]:
    response = requests.get(f"{base_url.rstrip('/')}/sessions/{session_id}", timeout=timeout)
    response.raise_for_status()
    return response.json()


def send_text_control(base_url: str, session_id: str, to: str, timeout: int) -> Dict[str, Any]:
    payload = {
        "sessionId": session_id,
        "to": to,
        "text": "Codex debug text control before voice-note send.",
    }
    response = requests.post(
        f"{base_url.rstrip('/')}/messages/send",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def generate_tts_wav(
    uniapi_base: str,
    api_key: str,
    model: str,
    voice: str,
    text_input: str,
    instructions: str,
    timeout: int,
) -> Tuple[bytes, str]:
    response = requests.post(
        f"{uniapi_base.rstrip('/')}/audio/speech",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "voice": voice,
            "input": text_input,
            "instructions": instructions,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.content, (response.headers.get("content-type") or "application/octet-stream")


def detect_extension(content_type: str, raw_bytes: bytes) -> str:
    lowered = str(content_type or "").lower()
    if "wav" in lowered or raw_bytes.startswith(b"RIFF"):
        return ".wav"
    if "ogg" in lowered or raw_bytes.startswith(b"OggS"):
        return ".ogg"
    if "mpeg" in lowered or raw_bytes.startswith(b"ID3") or raw_bytes[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
        return ".mp3"
    guessed = mimetypes.guess_extension(lowered.split(";", 1)[0].strip())
    return guessed or ".bin"


def resolve_ffmpeg_executable() -> str:
    if os.getenv("FFMPEG_BIN"):
        return os.environ["FFMPEG_BIN"]

    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - fallback path
        raise RuntimeError(
            "No ffmpeg binary found. Install ffmpeg or `python -m pip install imageio-ffmpeg`."
        ) from exc


def convert_to_ogg_opus(source_path: Path, output_path: Path) -> None:
    ffmpeg_bin = resolve_ffmpeg_executable()
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
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed:\n{process.stderr}")


def upload_to_catbox(file_path: Path, timeout: int) -> str:
    with file_path.open("rb") as file_obj:
        response = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (file_path.name, file_obj, "audio/ogg")},
            timeout=timeout,
        )
    response.raise_for_status()
    url = response.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"Unexpected Catbox response: {url}")
    return url


def upload_to_tmpfiles(file_path: Path, timeout: int) -> str:
    with file_path.open("rb") as file_obj:
        response = requests.post(
            "https://tmpfiles.org/api/v1/upload",
            files={"file": (file_path.name, file_obj, "audio/ogg")},
            timeout=timeout,
        )
    response.raise_for_status()
    payload = response.json()
    url = (((payload.get("data") or {}).get("url")) or "").strip()
    if not url.startswith("http"):
        raise RuntimeError(f"Unexpected tmpfiles response: {payload}")
    if url.startswith("http://tmpfiles.org/"):
        url = url.replace("http://tmpfiles.org/", "https://tmpfiles.org/dl/", 1)
    return url


def upload_public_audio(file_path: Path, provider: str, timeout: int) -> Tuple[str, str]:
    providers = ("catbox", "tmpfiles") if provider == "auto" else (provider,)
    last_error: Optional[str] = None

    for current in providers:
        try:
            if current == "catbox":
                return upload_to_catbox(file_path, timeout), current
            if current == "tmpfiles":
                return upload_to_tmpfiles(file_path, timeout), current
        except Exception as exc:
            last_error = f"{current}: {exc}"

    raise RuntimeError(f"All upload providers failed. Last error: {last_error}")


def send_voice_note(
    base_url: str,
    session_id: str,
    to: str,
    audio_url: str,
    mimetype: str,
    timeout: int,
) -> Dict[str, Any]:
    payload = {
        "sessionId": session_id,
        "to": to,
        "audioUrl": audio_url,
        "mimetype": mimetype,
        "ptt": True,
    }
    response = requests.post(
        f"{base_url.rstrip('/')}/messages/send",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def poll_recent_messages(
    base_url: str,
    session_id: str,
    jid: str,
    expected_id: str,
    timeout: int,
    total_seconds: int,
) -> Tuple[bool, Dict[str, Any]]:
    deadline = time.time() + max(total_seconds, 1)
    last_payload: Dict[str, Any] = {}

    while time.time() < deadline:
        response = requests.get(
            f"{base_url.rstrip('/')}/chats/{jid}/messages",
            params={"sessionId": session_id, "limit": 20},
            timeout=timeout,
        )
        response.raise_for_status()
        last_payload = response.json()
        messages = last_payload.get("messages") or []
        for item in messages:
            if str(item.get("id") or "") == expected_id:
                return True, last_payload
        time.sleep(2)

    return False, last_payload


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    require(bool(args.uniapi_key), "--uniapi-key or UNIAPI_KEY is required")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_dir).resolve() / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "session_id": args.session_id,
        "to": normalize_recipient(args.to),
        "paths": {},
    }

    log("session check")
    session_status = get_session_status(args.baileys_base, args.session_id, args.timeout_seconds)
    summary["session_status"] = session_status
    log("session status", session_status.get("status"))
    log("connected number", session_status.get("connectedNumber"))

    if args.send_text_control:
        log("sending text control")
        summary["text_control"] = send_text_control(
            args.baileys_base,
            args.session_id,
            normalize_recipient(args.to),
            args.timeout_seconds,
        )
        log("text control result", summary["text_control"].get("status"))

    public_audio_url = str(args.public_audio_url or "").strip()
    ogg_path: Optional[Path] = None

    if not public_audio_url:
        log("generating tts")
        raw_bytes, raw_content_type = generate_tts_wav(
            args.uniapi_base,
            args.uniapi_key,
            args.model,
            args.voice,
            args.input,
            args.instructions,
            args.timeout_seconds,
        )
        raw_extension = detect_extension(raw_content_type, raw_bytes)
        raw_path = output_dir / f"tts-raw{raw_extension}"
        raw_path.write_bytes(raw_bytes)
        summary["tts"] = {
            "raw_content_type": raw_content_type,
            "raw_bytes": len(raw_bytes),
        }
        summary["paths"]["tts_raw"] = str(raw_path)
        log("tts raw content-type", raw_content_type)
        log("tts raw bytes", len(raw_bytes))

        ogg_path = output_dir / "tts-voice-note.ogg"
        log("converting to ogg/opus")
        convert_to_ogg_opus(raw_path, ogg_path)
        summary["paths"]["tts_ogg"] = str(ogg_path)
        summary["tts"]["ogg_bytes"] = ogg_path.stat().st_size
        log("ogg bytes", ogg_path.stat().st_size)

        log("uploading public audio")
        public_audio_url, upload_provider = upload_public_audio(
            ogg_path,
            args.upload_provider,
            args.timeout_seconds,
        )
        summary["upload"] = {
            "provider": upload_provider,
            "public_audio_url": public_audio_url,
        }
        log("public audio url", public_audio_url)
    else:
        summary["upload"] = {
            "provider": "pre-supplied",
            "public_audio_url": public_audio_url,
        }

    log("sending voice note")
    send_result = send_voice_note(
        args.baileys_base,
        args.session_id,
        normalize_recipient(args.to),
        public_audio_url,
        args.mimetype,
        args.timeout_seconds,
    )
    summary["send_result"] = send_result
    write_json(output_dir / "send-result.json", send_result)

    provider_key = (((send_result.get("result") or {}).get("key")) or {})
    remote_jid = str(provider_key.get("remoteJid") or "").strip()
    provider_message_id = str(provider_key.get("id") or "").strip()
    summary["provider_message_id"] = provider_message_id
    summary["remote_jid"] = remote_jid
    log("provider message id", provider_message_id)
    log("remote jid", remote_jid)

    verified = False
    history_payload: Dict[str, Any] = {}
    if provider_message_id and remote_jid:
        log("polling chat history")
        verified, history_payload = poll_recent_messages(
            args.baileys_base,
            args.session_id,
            remote_jid,
            provider_message_id,
            args.timeout_seconds,
            args.poll_seconds,
        )
        summary["history_verified"] = verified
        write_json(output_dir / "history-poll.json", history_payload)
        log("history verified", verified)
    else:
        summary["history_verified"] = False

    summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if verified else 1


if __name__ == "__main__":
    sys.exit(main())
