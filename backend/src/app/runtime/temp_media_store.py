"""
Ephemeral temp media store for short-lived outbound media delivery.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Dict, Tuple
from uuid import uuid4


_TEMP_DIR = Path(os.getenv("TEMP_MEDIA_DIR", "/tmp/aiworkforme-temp-media"))
_TEMP_DIR.mkdir(parents=True, exist_ok=True)

_LOCK = Lock()
_INDEX: Dict[str, Dict[str, object]] = {}


def _cleanup_expired_locked(now: datetime) -> None:
    expired_tokens = [
        token
        for token, meta in _INDEX.items()
        if isinstance(meta.get("expires_at"), datetime) and meta["expires_at"] <= now
    ]
    for token in expired_tokens:
        meta = _INDEX.pop(token, {})
        path = meta.get("path")
        if isinstance(path, str):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except Exception:
                pass


def create_temp_media(content: bytes, mime_type: str, suffix: str = ".bin", ttl_seconds: int = 300) -> str:
    if not content:
        raise ValueError("content is required")
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    token = uuid4().hex
    file_name = f"{token}{suffix}"
    file_path = _TEMP_DIR / file_name
    file_path.write_bytes(content)

    now = datetime.utcnow()
    with _LOCK:
        _cleanup_expired_locked(now)
        _INDEX[token] = {
            "path": str(file_path),
            "mime_type": mime_type or "application/octet-stream",
            "file_name": file_name,
            "expires_at": now + timedelta(seconds=ttl_seconds),
        }
    return token


def consume_temp_media(token: str) -> Tuple[bytes, str, str]:
    if not token:
        raise KeyError("missing token")
    now = datetime.utcnow()
    with _LOCK:
        _cleanup_expired_locked(now)
        meta = _INDEX.pop(token, None)
    if not meta:
        raise KeyError("token not found or expired")

    path = str(meta.get("path") or "")
    mime_type = str(meta.get("mime_type") or "application/octet-stream")
    file_name = str(meta.get("file_name") or "media.bin")

    try:
        body = Path(path).read_bytes()
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except Exception:
            pass
    return body, mime_type, file_name


def delete_temp_media(token: str) -> None:
    if not token:
        return
    with _LOCK:
        meta = _INDEX.pop(token, None)
    if not meta:
        return
    path = str(meta.get("path") or "")
    if not path:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except Exception:
        pass

