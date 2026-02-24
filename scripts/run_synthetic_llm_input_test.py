#!/usr/bin/env python3
"""Run synthetic media input checks against inbound media preparation logic."""

import asyncio
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Python 3.9 compatibility stubs so we can import inbound media module
# without importing runtime modules that use Python 3.10+ syntax.
agent_runtime_stub = types.ModuleType("src.app.runtime.agent_runtime")


class _ConversationAgentRuntimeStub:
    def __init__(self, *_args, **_kwargs):
        pass


agent_runtime_stub.ConversationAgentRuntime = _ConversationAgentRuntimeStub
sys.modules["src.app.runtime.agent_runtime"] = agent_runtime_stub

leads_service_stub = types.ModuleType("src.app.runtime.leads_service")


def _noop_workspace(*_args, **_kwargs):
    return None


leads_service_stub.get_or_create_default_workspace = _noop_workspace
sys.modules["src.app.runtime.leads_service"] = leads_service_stub

notify_stub = types.ModuleType("src.app.inbound_worker_notify")


def _noop_notify(*_args, **_kwargs):
    return []


notify_stub.open_inbound_listen_connection = _noop_notify
notify_stub.wait_for_inbound_notify = _noop_notify
sys.modules["src.app.inbound_worker_notify"] = notify_stub

state_stub = types.ModuleType("src.app.inbound_worker_state")
state_stub.INBOUND_WORKER_STATE = {}
state_stub.get_worker_state_snapshot = lambda state: dict(state)
state_stub.iso_now = lambda: "1970-01-01T00:00:00Z"
state_stub.mark_worker_state = lambda state, **kwargs: state.update(kwargs)
sys.modules["src.app.inbound_worker_state"] = state_stub

from src.app import background_tasks_inbound as inbound  # noqa: E402


def _task_name(task: Any) -> str:
    return getattr(task, "value", str(task))


async def _run() -> int:
    originals = {
        "download_pdf": inbound._download_pdf_bytes,
        "extract_pdf": inbound._extract_pdf_text,
        "download_image": inbound._download_image_bytes,
    }

    async def _fake_download_pdf(_url: str) -> bytes:
        return b"%PDF-synthetic%"

    def _fake_extract_pdf(_bytes: bytes) -> Dict[str, Any]:
        return {
            "pages_read": 3,
            "text": "Synthetic PDF text page1 page2 page3",
            "text_truncated": False,
        }

    async def _fake_download_image(_url: str) -> bytes:
        return b"synthetic-image-bytes"

    inbound._download_pdf_bytes = _fake_download_pdf
    inbound._extract_pdf_text = _fake_extract_pdf
    inbound._download_image_bytes = _fake_download_image

    try:
        pdf_msg = SimpleNamespace(
            message_type="document",
            text_content="please check this",
            media_url="https://cdn.example.com/sample.pdf",
            raw_payload={
                "message": {
                    "documentMessage": {
                        "mimetype": "application/pdf",
                        "fileName": "sample.pdf",
                    }
                }
            },
        )
        image_msg = SimpleNamespace(
            message_type="image",
            text_content="what is in this image?",
            media_url="https://cdn.example.com/sample.jpg",
            raw_payload={
                "message": {
                    "imageMessage": {
                        "mimetype": "image/jpeg",
                        "fileName": "sample.jpg",
                    }
                }
            },
        )
        voice_msg = SimpleNamespace(
            message_type="audio",
            text_content=None,
            media_url="https://cdn.example.com/sample.ogg",
            raw_payload={
                "message": {
                    "audioMessage": {
                        "mimetype": "audio/ogg; codecs=opus",
                        "ptt": True,
                    }
                }
            },
        )

        pdf_prepared = await inbound._prepare_media_inbound_for_runtime(pdf_msg)
        image_prepared = await inbound._prepare_media_inbound_for_runtime(image_msg)
        voice_prepared = await inbound._prepare_media_inbound_for_runtime(voice_msg)

        results = {
            "pdf": {
                "task": _task_name(pdf_prepared.get("task")),
                "processing": pdf_prepared.get("processing"),
                "has_llm_image_payload": bool(pdf_prepared.get("llm_extra_params")),
                "prompt_has_pdf_phrase": "User attached a PDF document." in (pdf_prepared.get("user_message") or ""),
            },
            "image": {
                "task": _task_name(image_prepared.get("task")),
                "processing": image_prepared.get("processing"),
                "has_llm_image_payload": bool((image_prepared.get("llm_extra_params") or {}).get("image_content")),
                "image_mime_type": (image_prepared.get("llm_extra_params") or {}).get("image_mime_type"),
                "prompt_has_image_phrase": "User attached an image." in (image_prepared.get("user_message") or ""),
            },
            "voice_note": {
                "task": _task_name(voice_prepared.get("task")),
                "processing": voice_prepared.get("processing"),
                "llm_extra_params": voice_prepared.get("llm_extra_params"),
                "note": "voice_note workflow not wired yet in inbound worker",
            },
        }

        checks = {
            "pdf_task_is_pdf": results["pdf"]["task"] == "pdf",
            "pdf_status_ok": (results["pdf"]["processing"] or {}).get("status") == "ok",
            "image_task_is_images": results["image"]["task"] == "images",
            "image_status_ok": (results["image"]["processing"] or {}).get("status") == "ok",
            "image_bytes_attached": results["image"]["has_llm_image_payload"] is True,
            "voice_currently_falls_back_to_conversation": results["voice_note"]["task"] == "conversation",
        }
        success = all(checks.values())

        output = {
            "success": success,
            "checks": checks,
            "results": results,
        }
        print(json.dumps(output, indent=2))
        return 0 if success else 1
    finally:
        inbound._download_pdf_bytes = originals["download_pdf"]
        inbound._extract_pdf_text = originals["extract_pdf"]
        inbound._download_image_bytes = originals["download_image"]


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
