"""Inbound worker for processing inbound unified messages through agent runtime."""
import asyncio
import io
import importlib
import inspect
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlmodel import Session, select

from src.app.runtime.agent_runtime import ConversationAgentRuntime
from src.app.runtime.leads_service import get_or_create_default_workspace
from src.app.runtime.sales_materials import (
    SALES_MATERIAL_MAX_BYTES,
    list_agent_sales_materials,
    resolve_sales_material_public_url,
    sales_material_kind_for_material,
    thread_sales_material_state,
)
from src.app.inbound_worker_notify import (
    open_inbound_listen_connection,
    wait_for_inbound_notify,
)
from src.app.inbound_worker_state import (
    INBOUND_WORKER_STATE,
    get_worker_state_snapshot,
    iso_now,
    mark_worker_state,
)
logger = logging.getLogger(__name__)
INBOUND_POLL_SECONDS = float(os.getenv("MESSAGING_INBOUND_POLL_SECONDS", "2"))
INBOUND_BATCH_SIZE = int(os.getenv("MESSAGING_INBOUND_BATCH_SIZE", "5"))
INBOUND_NOTIFY_CHANNEL = os.getenv("MESSAGING_INBOUND_NOTIFY_CHANNEL", "inbound_new_message")
PDF_MAX_PAGES = 5
PDF_MAX_CHARS = 12000
# Keep inbound PDF processing aligned with the same 30 MB limit used for
# agent sales-material uploads so the UX stays consistent.
PDF_MAX_DOWNLOAD_BYTES = SALES_MATERIAL_MAX_BYTES
IMAGE_MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024
AUDIO_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
_ENGINE = None
_LLM_ROUTER = None
_DB_MODELS = None
def _iso_now() -> str:
    return iso_now()
def _mark_worker_state(**kwargs):
    mark_worker_state(INBOUND_WORKER_STATE, **kwargs)
def get_inbound_worker_debug_snapshot() -> Dict[str, Any]:
    return get_worker_state_snapshot(INBOUND_WORKER_STATE)
def _get_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = importlib.import_module("src.infra.database").engine
    return _ENGINE
def _get_llm_router():
    global _LLM_ROUTER
    if _LLM_ROUTER is None:
        _LLM_ROUTER = importlib.import_module("src.adapters.api.dependencies").llm_router
    return _LLM_ROUTER
def _get_db_models():
    global _DB_MODELS
    if _DB_MODELS is None:
        importlib.import_module("src.adapters.db.channel_models")
        messaging = importlib.import_module("src.adapters.db.messaging_models")
        crm = importlib.import_module("src.adapters.db.crm_models")
        agent_models = importlib.import_module("src.adapters.db.agent_models")
        _DB_MODELS = (
            messaging.UnifiedMessage,
            messaging.UnifiedThread,
            messaging.OutboundQueue,
            crm.Lead,
            crm.Workspace,
            agent_models.Agent,
        )
    return _DB_MODELS
def _resolve_thread_agent(session: Session, message: Any) -> Optional[Any]:
    _, UnifiedThread, _, Lead, Workspace, Agent = _get_db_models()
    if not message.thread_id:
        return None

    thread = session.get(UnifiedThread, message.thread_id)
    if not thread or thread.tenant_id != message.tenant_id:
        return None

    if thread.agent_id is None:
        lead = session.get(Lead, message.lead_id)
        if not lead or lead.tenant_id != message.tenant_id:
            return None

        candidate_agent_id = getattr(lead, "agent_id", None)

        if candidate_agent_id is None and getattr(message, "channel_session_id", None):
            preferred_agent = session.exec(
                select(Agent)
                .where(
                    Agent.tenant_id == message.tenant_id,
                    Agent.preferred_channel_session_id == message.channel_session_id,
                )
                .order_by(Agent.id.asc())
            ).first()
            candidate_agent_id = preferred_agent.id if preferred_agent else None

        if candidate_agent_id is None:
            workspace = session.get(Workspace, lead.workspace_id)
            candidate_agent_id = (
                workspace.agent_id
                if workspace and workspace.tenant_id == message.tenant_id
                else None
            )

        if candidate_agent_id is None:
            fallback = session.exec(
                select(Agent)
                .where(Agent.tenant_id == message.tenant_id)
                .order_by(Agent.id.asc())
            ).first()
            candidate_agent_id = fallback.id if fallback else None

        if candidate_agent_id is None:
            logger.warning(
                "No agent found for tenant_id=%s, message_id=%s — marking human_takeover",
                message.tenant_id, message.id,
            )
            return None

        thread.agent_id = candidate_agent_id
        thread.updated_at = datetime.now(timezone.utc)
        session.add(thread)
        session.commit()
        session.refresh(thread)

    agent = session.get(Agent, thread.agent_id)
    if not agent or agent.tenant_id != message.tenant_id:
        return None
    return agent
def _build_thread_history(session: Session, message: Any) -> List[Dict[str, str]]:
    UnifiedMessage, _, _, _, _, _ = _get_db_models()
    if not message.thread_id:
        return []

    items = session.exec(
        select(UnifiedMessage)
        .where(
            UnifiedMessage.tenant_id == message.tenant_id,
            UnifiedMessage.thread_id == message.thread_id,
            UnifiedMessage.id != message.id,
        )
        .order_by(UnifiedMessage.created_at.desc())
        .limit(12)
    ).all()
    items.reverse()

    history: List[Dict[str, str]] = []
    for item in items:
        if not item.text_content:
            continue
        role = "user" if item.direction == "inbound" else "assistant"
        history.append({"role": role, "content": item.text_content})
    return history
def _enqueue_outbound_reply(
    session: Session,
    inbound_message: Any,
    agent_id: int,
    text: str,
    message_type: str = "text",
    media_url: Optional[str] = None,
    extra_raw_payload: Optional[Dict[str, Any]] = None,
    ai_trace: Optional[Dict[str, Any]] = None,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    llm_prompt_tokens: Optional[int] = None,
    llm_completion_tokens: Optional[int] = None,
    llm_total_tokens: Optional[int] = None,
    llm_estimated_cost_usd: Optional[float] = None,
) -> Any:
    UnifiedMessage, _, OutboundQueue, _, _, _ = _get_db_models()
    now = datetime.now(timezone.utc)
    outbound = UnifiedMessage(
        tenant_id=inbound_message.tenant_id,
        lead_id=inbound_message.lead_id,
        thread_id=inbound_message.thread_id,
        channel_session_id=inbound_message.channel_session_id,
        channel=inbound_message.channel,
        external_message_id=f"out_{uuid4().hex}",
        direction="outbound",
        message_type=message_type,
        text_content=text,
        media_url=media_url,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_prompt_tokens=llm_prompt_tokens,
        llm_completion_tokens=llm_completion_tokens,
        llm_total_tokens=llm_total_tokens,
        llm_estimated_cost_usd=llm_estimated_cost_usd,
        raw_payload={
            "source": "ai_agent",
            "inbound_message_id": inbound_message.id,
            "agent_id": agent_id,
            "ai_trace": ai_trace or {},
            **(extra_raw_payload or {}),
        },
        delivery_status="queued",
        created_at=now,
        updated_at=now,
    )
    session.add(outbound)
    session.commit()
    session.refresh(outbound)

    queue = OutboundQueue(
        tenant_id=inbound_message.tenant_id,
        message_id=outbound.id,
        channel=inbound_message.channel,
        channel_session_id=inbound_message.channel_session_id,
        status="queued",
        retry_count=0,
        next_attempt_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(queue)
    session.commit()
    return outbound


def _enqueue_sales_material_reply(
    session: Session,
    inbound_message: Any,
    agent_id: int,
    material: Any,
    planner_trace: Optional[Dict[str, Any]] = None,
) -> Any:
    UnifiedMessage, _, OutboundQueue, _, _, _ = _get_db_models()
    now = datetime.now(timezone.utc)
    source_type = str(getattr(material, "source_type", "file") or "file").strip().lower()
    resolved_url = resolve_sales_material_public_url(material)
    if not resolved_url:
        raise RuntimeError(f"Sales material {getattr(material, 'id', '?')} has no delivery URL")

    outbound = UnifiedMessage(
        tenant_id=inbound_message.tenant_id,
        lead_id=inbound_message.lead_id,
        thread_id=inbound_message.thread_id,
        channel_session_id=inbound_message.channel_session_id,
        channel=inbound_message.channel,
        external_message_id=f"out_{uuid4().hex}",
        direction="outbound",
        message_type="text",
        text_content=resolved_url,
        media_url=None,
        raw_payload={
            "source": "ai_agent_sales_material",
            "inbound_message_id": inbound_message.id,
            "agent_id": agent_id,
            "sales_material_id": material.id,
            "sales_material_ids": [material.id],
            "file_name": material.filename,
            "mime_type": material.media_type,
            "source_type": source_type,
            "url": resolved_url,
            "kind": sales_material_kind_for_material(material),
            "delivery_mode": "url_only",
            "planner_trace": planner_trace or {},
        },
        delivery_status="queued",
        created_at=now,
        updated_at=now,
    )
    session.add(outbound)
    session.commit()
    session.refresh(outbound)

    queue = OutboundQueue(
        tenant_id=inbound_message.tenant_id,
        message_id=outbound.id,
        channel=inbound_message.channel,
        channel_session_id=inbound_message.channel_session_id,
        status="queued",
        retry_count=0,
        next_attempt_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(queue)
    session.commit()
    return outbound


def _filter_supported_run_turn_kwargs(run_turn_callable: Any, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keep inbound processing resilient during rolling deploys where the worker and
    runtime signatures may not be upgraded in lockstep yet.
    """
    try:
        signature = inspect.signature(run_turn_callable)
    except (TypeError, ValueError):
        return kwargs

    parameters = signature.parameters
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters.values()):
        return kwargs

    supported = {key: value for key, value in kwargs.items() if key in parameters}
    skipped = sorted(set(kwargs) - set(supported))
    if skipped:
        logger.warning(
            "ConversationAgentRuntime.run_turn does not accept kwargs=%s; skipping them for compatibility",
            ",".join(skipped),
        )
    return supported


async def _enqueue_segmented_reply(
    session: Session,
    inbound_message: Any,
    agent_id: int,
    full_text: str,
    delay_ms: int = 800,
    ai_trace: Optional[Dict[str, Any]] = None,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    llm_prompt_tokens: Optional[int] = None,
    llm_completion_tokens: Optional[int] = None,
    llm_total_tokens: Optional[int] = None,
    llm_estimated_cost_usd: Optional[float] = None,
) -> List[Any]:
    """
    Splits full_text on '|||', enqueues each non-empty segment as a separate
    outbound message, with asyncio.sleep(delay_ms/1000) between segments to
    simulate natural human typing pacing on WhatsApp.
    """
    segments = [s.strip() for s in full_text.split("|||") if s.strip()]
    if not segments:
        segments = [full_text.strip()]

    enqueued = []
    for idx, segment in enumerate(segments):
        if idx > 0 and delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)
        outbound = _enqueue_outbound_reply(
            session=session,
            inbound_message=inbound_message,
            agent_id=agent_id,
            text=segment,
            ai_trace={**(ai_trace or {}), "segment_index": idx, "segment_total": len(segments)},
            llm_provider=llm_provider,
            llm_model=llm_model,
            # Only attribute token costs to the first segment to avoid double-counting
            llm_prompt_tokens=llm_prompt_tokens if idx == 0 else None,
            llm_completion_tokens=llm_completion_tokens if idx == 0 else None,
            llm_total_tokens=llm_total_tokens if idx == 0 else None,
            llm_estimated_cost_usd=llm_estimated_cost_usd if idx == 0 else None,
        )
        enqueued.append(outbound)
        logger.info(
            "Segment %d/%d enqueued (message_id=%s): %.60s…",
            idx + 1, len(segments), outbound.id, segment,
        )
    return enqueued


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _material_text_blob(item: Dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "").strip().lower()
        for key in ("filename", "description", "kind", "media_type", "url")
    )


def _explicit_sales_material_terms(*texts: str) -> List[str]:
    combined = " ".join(str(text or "").lower() for text in texts)
    patterns = [
        ("brochure", r"\bbrochure\b"),
        ("catalog", r"\bcatalog(?:ue)?\b"),
        ("pdf", r"\bpdf\b"),
        ("deck", r"\bdeck\b"),
        ("company profile", r"\bcompany profile\b"),
        ("pricing", r"\bpricing\b|\bprice list\b"),
        ("spec", r"\bspec(?:s)?\b|\bdatasheet\b|\bdata sheet\b"),
        ("manual", r"\bmanual\b"),
        ("proposal", r"\bproposal\b"),
        ("image", r"\bimage\b|\bphoto\b|\bpicture\b"),
        ("flyer", r"\bflyer\b|\bleaflet\b"),
    ]
    found = [label for label, pattern in patterns if re.search(pattern, combined)]
    if re.search(r"\b(send|share|attach|upload|show|give)\b", combined) and re.search(
        r"\b(file|document|material|brochure|catalog(?:ue)?|pdf|image|photo|picture)\b",
        combined,
    ):
        found.append("attachment")
    return list(dict.fromkeys(found))


def _heuristic_sales_material_ids(
    options: List[Dict[str, Any]],
    user_message: str,
    reply_text: str,
) -> List[int]:
    terms = _explicit_sales_material_terms(user_message, reply_text)
    if not terms:
        return []

    combined = " ".join([str(user_message or "").lower(), str(reply_text or "").lower()])
    allows_resend = bool(re.search(r"\b(again|resend|re-send|another copy|download again|review again)\b", combined))
    wants_image = any(term in {"image", "flyer"} for term in terms)
    wants_document = any(
        term in {"brochure", "catalog", "pdf", "deck", "company profile", "pricing", "spec", "manual", "proposal"}
        for term in terms
    )

    scored: List[tuple[int, int]] = []
    for item in options:
        already_sent = bool(item.get("already_sent"))
        if already_sent and not allows_resend:
            continue

        base_score = 0
        text_blob = _material_text_blob(item)
        kind = str(item.get("kind") or "").strip().lower()
        for term in terms:
            if term == "attachment":
                continue
            if term in text_blob:
                base_score += 5
        if wants_image and kind == "image":
            base_score += 4
        if wants_document and kind == "document":
            base_score += 4
        if str(item.get("filename") or "").strip().lower().endswith(".pdf") and wants_document:
            base_score += 2

        score = base_score
        if base_score > 0 and not already_sent:
            score += 1

        if score > 0 and item.get("id") is not None:
            scored.append((int(item["id"]), score))

    if scored:
        scored.sort(key=lambda row: (-row[1], row[0]))
        return [material_id for material_id, _score in scored[:2]]

    eligible = [
        int(item["id"])
        for item in options
        if item.get("id") is not None and (allows_resend or not item.get("already_sent"))
    ]
    if len(eligible) == 1 and "attachment" in terms:
        return eligible
    return []


async def _plan_sales_material_sends(
    session: Session,
    inbound_message: Any,
    agent: Any,
    user_message: str,
    reply_text: str,
) -> List[Dict[str, Any]]:
    if inbound_message.channel != "whatsapp" or not inbound_message.thread_id:
        return []

    materials = list_agent_sales_materials(session, int(inbound_message.tenant_id), int(agent.id))
    if not materials:
        return []

    sent_state = thread_sales_material_state(session, int(inbound_message.tenant_id), inbound_message.thread_id)
    options = [
        {
            "id": int(material.id),
            "filename": material.filename,
            "description": material.description,
            "media_type": material.media_type,
            "kind": sales_material_kind_for_material(material),
            "source_type": str(getattr(material, "source_type", "file") or "file").strip().lower(),
            "url": resolve_sales_material_public_url(material),
            "already_sent": int(material.id) in sent_state,
            "send_count": int((sent_state.get(int(material.id)) or {}).get("count", 0) or 0),
            "last_sent_at": (sent_state.get(int(material.id)) or {}).get("last_sent_at"),
        }
        for material in materials
        if material.id is not None
    ]
    if not options:
        return []

    heuristic_ids = _heuristic_sales_material_ids(options, user_message, reply_text)
    if heuristic_ids:
        selected: List[Dict[str, Any]] = []
        for material in materials:
            material_id = int(material.id or 0)
            if material_id in heuristic_ids:
                selected.append(
                    {
                        "material": material,
                        "planner_trace": {
                            "reason": "heuristic explicit sales-material request",
                            "selected_material_ids": heuristic_ids,
                            "selection_mode": "heuristic",
                        },
                    }
                )
        if selected:
            return selected

    llm_task = importlib.import_module("src.infra.llm.schemas").LLMTask
    planner_messages = [
        {
            "role": "system",
            "content": (
                "You decide whether a WhatsApp AI assistant should send any sales materials after its text reply. "
                "Return JSON only with keys material_ids and reason. "
                "Rules: choose at most 2 materials, only choose directly relevant materials, "
                "avoid re-sending already-sent materials unless the user clearly asks to resend/review/download them again."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Agent name: {agent.name}\n"
                f"Customer message:\n{user_message or '(empty)'}\n\n"
                f"Assistant reply:\n{reply_text or '(empty)'}\n\n"
                "Available materials JSON:\n"
                f"{json.dumps(options, ensure_ascii=True)}\n\n"
                'Return strict JSON like {"material_ids":[1],"reason":"short reason"}'
            ),
        },
    ]

    try:
        response = await _get_llm_router().execute(
            task=llm_task.CONVERSATION,
            messages=planner_messages,
            temperature=0.1,
            max_tokens=180,
        )
    except Exception as exc:
        logger.warning(
            "Sales material planner failed for inbound message_id=%s: %s",
            inbound_message.id,
            exc,
        )
        return []

    parsed = _extract_json_object(response.content or "")
    chosen_ids = parsed.get("material_ids")
    if not isinstance(chosen_ids, list):
        return []

    valid_ids = []
    for item in chosen_ids:
        if isinstance(item, int):
            valid_ids.append(item)
        elif isinstance(item, str) and item.isdigit():
            valid_ids.append(int(item))
    valid_ids = list(dict.fromkeys(valid_ids))[:2]
    if not valid_ids:
        return []

    selected: List[Dict[str, Any]] = []
    by_id = {int(item["id"]): item for item in options}
    for material in materials:
        material_id = int(material.id or 0)
        if material_id in valid_ids and material_id in by_id:
            selected.append(
                {
                    "material": material,
                    "planner_trace": {
                        "reason": str(parsed.get("reason") or "").strip()[:300],
                        "selected_material_ids": valid_ids,
                        "model_output": (response.content or "")[:1200],
                    },
                }
            )
    return selected



def _message_type(message: Any) -> str:
    return str(getattr(message, "message_type", "") or "").strip().lower()


def _message_payload(message: Any) -> Dict[str, Any]:
    payload = getattr(message, "raw_payload", {})
    return payload if isinstance(payload, dict) else {}


def _message_media_url(message: Any) -> str:
    direct = str(getattr(message, "media_url", "") or "").strip()
    if direct:
        return direct
    payload = _message_payload(message)
    for key in ("media_url", "mediaUrl", "url", "downloadUrl", "download_url"):
        fallback = str(payload.get(key, "") or "").strip()
        if fallback:
            return fallback

    raw_message = payload.get("message")
    if isinstance(raw_message, dict):
        for container_key in (
            "documentMessage",
            "imageMessage",
            "audioMessage",
            "videoMessage",
        ):
            media_body = raw_message.get(container_key)
            if not isinstance(media_body, dict):
                continue
            for key in ("url", "mediaUrl", "media_url", "downloadUrl", "download_url"):
                nested = str(media_body.get(key, "") or "").strip()
                if nested:
                    return nested

    media_obj = payload.get("media")
    if isinstance(media_obj, dict):
        for key in ("url", "mediaUrl", "media_url", "downloadUrl", "download_url"):
            nested = str(media_obj.get(key, "") or "").strip()
            if nested:
                return nested

    return ""


def _pdf_filename(message: Any) -> str:
    payload = _message_payload(message)
    raw_message = payload.get("message")
    if isinstance(raw_message, dict):
        doc = raw_message.get("documentMessage")
        if isinstance(doc, dict):
            candidate = str(
                doc.get("fileName") or doc.get("filename") or doc.get("title") or ""
            ).strip()
            if candidate:
                return candidate
    candidate = str(payload.get("filename") or "").strip()
    return candidate


def _pdf_mime_type(message: Any) -> str:
    payload = _message_payload(message)
    raw_message = payload.get("message")
    if isinstance(raw_message, dict):
        doc = raw_message.get("documentMessage")
        if isinstance(doc, dict):
            candidate = str(doc.get("mimetype") or doc.get("mime_type") or "").strip().lower()
            if candidate:
                return candidate
    candidate = str(payload.get("mime_type") or "").strip().lower()
    return candidate


def _is_pdf_message(message: Any) -> bool:
    msg_type = _message_type(message)
    if msg_type == "pdf":
        return True
    if msg_type not in {"document", "file"}:
        return False

    mime_type = _pdf_mime_type(message)
    if mime_type == "application/pdf":
        return True

    filename = _pdf_filename(message).lower()
    if filename.endswith(".pdf"):
        return True

    media_url = _message_media_url(message)
    if not media_url:
        return False
    return urlparse(media_url).path.lower().endswith(".pdf")


async def _download_pdf_bytes(media_url: str) -> bytes:
    parsed = urlparse(media_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Unsupported media_url scheme for PDF download")
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        response = await client.get(media_url)
        response.raise_for_status()
        data = response.content
        if not data:
            raise ValueError("Downloaded PDF is empty")
        if len(data) > PDF_MAX_DOWNLOAD_BYTES:
            raise ValueError(
                f"PDF exceeds max allowed size ({PDF_MAX_DOWNLOAD_BYTES} bytes)"
            )
        return data


async def _download_image_bytes(media_url: str) -> bytes:
    parsed = urlparse(media_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Unsupported media_url scheme for image download")
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        response = await client.get(media_url)
        response.raise_for_status()
        data = response.content
        if not data:
            raise ValueError("Downloaded image is empty")
        if len(data) > IMAGE_MAX_DOWNLOAD_BYTES:
            raise ValueError(
                f"Image exceeds max allowed size ({IMAGE_MAX_DOWNLOAD_BYTES} bytes)"
            )
        return data


async def _download_audio_bytes(media_url: str) -> bytes:
    parsed = urlparse(media_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Unsupported media_url scheme for audio download")
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(media_url)
        response.raise_for_status()
        data = response.content
        if not data:
            raise ValueError("Downloaded audio is empty")
        if len(data) > AUDIO_MAX_DOWNLOAD_BYTES:
            raise ValueError(
                f"Audio exceeds max allowed size ({AUDIO_MAX_DOWNLOAD_BYTES} bytes)"
            )
        return data


def _extract_pdf_text(pdf_bytes: bytes) -> Dict[str, Any]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:
        raise RuntimeError("pypdf is required for PDF processing") from exc

    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_to_read = min(len(reader.pages), PDF_MAX_PAGES)
    page_chunks: List[str] = []
    for idx in range(pages_to_read):
        page_text = (reader.pages[idx].extract_text() or "").strip()
        if page_text:
            page_chunks.append(f"[Page {idx + 1}]\n{page_text}")

    combined = "\n\n".join(page_chunks).strip()
    truncated = False
    if len(combined) > PDF_MAX_CHARS:
        combined = combined[:PDF_MAX_CHARS]
        truncated = True

    return {
        "pages_read": pages_to_read,
        "text": combined,
        "text_truncated": truncated,
    }


def _image_mime_type(message: Any) -> str:
    payload = _message_payload(message)
    raw_message = payload.get("message")
    if isinstance(raw_message, dict):
        image_body = raw_message.get("imageMessage")
        if isinstance(image_body, dict):
            candidate = str(
                image_body.get("mimetype") or image_body.get("mime_type") or ""
            ).strip().lower()
            if candidate:
                return candidate
    candidate = str(payload.get("mime_type") or "").strip().lower()
    return candidate


def _image_filename(message: Any) -> str:
    payload = _message_payload(message)
    raw_message = payload.get("message")
    if isinstance(raw_message, dict):
        image_body = raw_message.get("imageMessage")
        if isinstance(image_body, dict):
            candidate = str(image_body.get("fileName") or image_body.get("filename") or "").strip()
            if candidate:
                return candidate
    candidate = str(payload.get("filename") or "").strip()
    return candidate


def _is_image_message(message: Any) -> bool:
    msg_type = _message_type(message)
    if msg_type in {"image", "photo"}:
        return True
    mime_type = _image_mime_type(message)
    if mime_type.startswith("image/"):
        return True
    payload = _message_payload(message)
    raw_message = payload.get("message")
    return isinstance(raw_message, dict) and isinstance(
        raw_message.get("imageMessage"), dict
    )


def _voice_mime_type(message: Any) -> str:
    payload = _message_payload(message)
    raw_message = payload.get("message")
    if isinstance(raw_message, dict):
        audio_body = raw_message.get("audioMessage")
        if isinstance(audio_body, dict):
            candidate = str(
                audio_body.get("mimetype") or audio_body.get("mime_type") or ""
            ).strip().lower()
            if candidate:
                return candidate
    candidate = str(payload.get("mime_type") or "").strip().lower()
    return candidate


def _voice_filename(message: Any) -> str:
    payload = _message_payload(message)
    raw_message = payload.get("message")
    if isinstance(raw_message, dict):
        audio_body = raw_message.get("audioMessage")
        if isinstance(audio_body, dict):
            candidate = str(audio_body.get("fileName") or audio_body.get("filename") or "").strip()
            if candidate:
                return candidate
    candidate = str(payload.get("filename") or "").strip()
    return candidate


def _is_voice_message(message: Any) -> bool:
    msg_type = _message_type(message)
    if msg_type in {"audio", "voice", "voice_note", "ptt"}:
        return True
    mime_type = _voice_mime_type(message)
    if mime_type.startswith("audio/"):
        return True
    payload = _message_payload(message)
    raw_message = payload.get("message")
    return isinstance(raw_message, dict) and isinstance(
        raw_message.get("audioMessage"), dict
    )


def _is_any_media_message(message: Any) -> bool:
    msg_type = _message_type(message)
    if msg_type in {"image", "photo", "video", "audio", "voice", "voice_note", "ptt", "document", "file", "pdf"}:
        return True
    return _is_pdf_message(message) or _is_image_message(message) or _is_voice_message(message)


async def _transcribe_voice_note(audio_bytes: bytes, mime_type: str, media_url: str = "") -> str:
    llm_task = importlib.import_module("src.infra.llm.schemas").LLMTask
    response = await _get_llm_router().execute(
        task=llm_task.VOICE_NOTE,
        messages=[
            {
                "role": "system",
                "content": (
                    "You transcribe voice notes. Return plain transcript text only. "
                    "Do not add explanations."
                ),
            },
            {
                "role": "user",
                "content": "Transcribe this voice note to text.",
            },
        ],
        temperature=0.0,
        max_tokens=1200,
        # Default: gpt-4o-transcribe via /v1/audio/transcriptions (OpenAI-compatible).
        # To use Alibaba ASR instead, set model="qwen3-asr-flash-filetrans" here or via
        # the llm_task_model_config DB setting for the VOICE_NOTE task.
        model="gpt-4o-transcribe",
        uniapi_schema="openai_audio_transcriptions",
        audio_content=audio_bytes,
        audio_mime_type=mime_type,
        audio_url=(str(media_url).strip() or None),
        media_url=(str(media_url).strip() or None),
    )
    transcript = (response.content or "").strip()
    if not transcript:
        raise ValueError("Voice note transcription returned empty text")
    return transcript


async def _prepare_media_inbound_for_runtime(message: Any) -> Dict[str, Any]:
    llm_task = importlib.import_module("src.infra.llm.schemas").LLMTask
    base_text = str(getattr(message, "text_content", "") or "").strip()
    prepared: Dict[str, Any] = {
        "task": llm_task.CONVERSATION,
        "user_message": base_text,
        "processing": None,
        "llm_extra_params": None,
        "should_run_runtime": True,
        "skip_reason": None,
    }

    if _is_pdf_message(message):
        media_url = _message_media_url(message)
        filename = _pdf_filename(message)
        processing: Dict[str, Any] = {
            "type": "pdf",
            "workflow_task": llm_task.PDF.value,
            "media_url": media_url or None,
            "filename": filename or None,
            "mime_type": _pdf_mime_type(message) or None,
            "status": "pending",
        }

        pdf_text = ""
        pages_read = 0
        if not media_url:
            processing["status"] = "error"
            processing["error"] = "No media_url found for PDF message"
        else:
            try:
                pdf_bytes = await _download_pdf_bytes(media_url)
                extraction = _extract_pdf_text(pdf_bytes)
                pdf_text = extraction.get("text", "") or ""
                pages_read = int(extraction.get("pages_read", 0) or 0)
                processing["status"] = "ok"
                processing["pages_read"] = pages_read
                processing["text_truncated"] = bool(extraction.get("text_truncated", False))
                processing["text_chars"] = len(pdf_text)
            except Exception as exc:
                processing["status"] = "error"
                processing["error"] = str(exc)[:500]

        prompt_parts: List[str] = []
        if base_text:
            prompt_parts.append(f"User message: {base_text}")
        prompt_parts.append("User attached a PDF document.")
        if filename:
            prompt_parts.append(f"PDF filename: {filename}")
        if processing["status"] == "ok":
            prompt_parts.append(
                "PDF extracted text "
                f"(first {pages_read} page(s), max {PDF_MAX_PAGES}):\n"
                f"{pdf_text or '[No readable text extracted]'}"
            )
        else:
            prompt_parts.append(
                f"PDF extraction failed: {processing.get('error', 'unknown error')}"
            )

        prompt_parts.append(
            "Based on conversation history and this PDF content, "
            "infer why the user sent the PDF, then respond helpfully."
        )

        prepared["task"] = llm_task.PDF
        prepared["user_message"] = "\n\n".join(prompt_parts).strip()
        prepared["processing"] = processing
        if processing.get("status") != "ok" and not base_text:
            prepared["should_run_runtime"] = False
            prepared["skip_reason"] = "PDF_PROCESSING_FAILED_NO_TEXT"
        return prepared

    if _is_image_message(message):
        media_url = _message_media_url(message)
        mime_type = _image_mime_type(message) or "image/jpeg"
        filename = _image_filename(message)
        processing = {
            "type": "image",
            "workflow_task": llm_task.IMAGES.value,
            "media_url": media_url or None,
            "filename": filename or None,
            "mime_type": mime_type,
            "status": "pending",
        }

        image_bytes: Optional[bytes] = None
        if not media_url:
            processing["status"] = "error"
            processing["error"] = "No media_url found for image message"
        else:
            try:
                image_bytes = await _download_image_bytes(media_url)
                processing["status"] = "ok"
                processing["bytes"] = len(image_bytes)
            except Exception as exc:
                processing["status"] = "error"
                processing["error"] = str(exc)[:500]

        prompt_parts = []
        if base_text:
            prompt_parts.append(f"User message: {base_text}")
        prompt_parts.append("User attached an image.")
        if filename:
            prompt_parts.append(f"Image filename: {filename}")
        prompt_parts.append(f"Image mime type: {mime_type}")
        if processing.get("status") != "ok":
            prompt_parts.append(
                f"Image fetch failed: {processing.get('error', 'unknown error')}"
            )
        prompt_parts.append(
            "Based on conversation history and this image, infer why the user sent it, then respond helpfully."
        )

        prepared["task"] = llm_task.IMAGES
        prepared["user_message"] = "\n\n".join(prompt_parts).strip()
        prepared["processing"] = processing
        if image_bytes is not None:
            prepared["llm_extra_params"] = {
                "image_content": image_bytes,
                "image_mime_type": mime_type,
            }
        if processing.get("status") != "ok" and not base_text:
            prepared["should_run_runtime"] = False
            prepared["skip_reason"] = "IMAGE_PROCESSING_FAILED_NO_TEXT"
        return prepared

    if _is_voice_message(message):
        media_url = _message_media_url(message)
        mime_type = _voice_mime_type(message) or "audio/ogg"
        filename = _voice_filename(message)
        processing: Dict[str, Any] = {
            "type": "voice_note",
            "workflow_task": llm_task.VOICE_NOTE.value,
            "media_url": media_url or None,
            "filename": filename or None,
            "mime_type": mime_type,
            "status": "pending",
        }

        transcript = ""
        if not media_url:
            processing["status"] = "error"
            processing["error"] = "No media_url found for voice note message"
        else:
            try:
                audio_bytes = await _download_audio_bytes(media_url)
                processing["bytes"] = len(audio_bytes)
                transcript = await _transcribe_voice_note(audio_bytes, mime_type, media_url)
                processing["status"] = "ok"
                processing["transcript_chars"] = len(transcript)
            except Exception as exc:
                processing["status"] = "error"
                processing["error"] = str(exc)[:500]

        prompt_parts = []
        if base_text:
            prompt_parts.append(f"User message: {base_text}")
        prompt_parts.append("User sent a voice note.")
        if filename:
            prompt_parts.append(f"Voice note filename: {filename}")
        prompt_parts.append(f"Voice note mime type: {mime_type}")
        if processing["status"] == "ok":
            prompt_parts.append(
                "Voice note transcript:\n"
                f"{transcript}"
            )
        else:
            prompt_parts.append(
                f"Voice note processing failed: {processing.get('error', 'unknown error')}"
            )

        prompt_parts.append(
            "Based on conversation history and this voice note transcript, infer intent and respond helpfully."
        )

        prepared["task"] = llm_task.CONVERSATION
        prepared["user_message"] = "\n\n".join(prompt_parts).strip()
        prepared["processing"] = processing
        if processing.get("status") != "ok" and not base_text:
            prepared["should_run_runtime"] = False
            prepared["skip_reason"] = "VOICE_PROCESSING_FAILED_NO_TEXT"
        return prepared

    if _is_any_media_message(message) and not base_text:
        prepared["processing"] = {
            "type": _message_type(message) or "media",
            "status": "error",
            "error": "Unsupported or unprocessable media without text context",
        }
        prepared["should_run_runtime"] = False
        prepared["skip_reason"] = "UNPROCESSABLE_MEDIA_NO_TEXT"

    return prepared


async def _process_one_inbound(session: Session, message: Any):
    _, _, _, Lead, _, _ = _get_db_models()
    if message.delivery_status != "inbound_processing":
        message.delivery_status = "inbound_processing"
        message.updated_at = datetime.now(timezone.utc)
        session.add(message)
        session.commit()
        session.refresh(message)

    agent = _resolve_thread_agent(session, message)
    if not agent:
        message.delivery_status = "inbound_human_takeover"
        message.updated_at = datetime.now(timezone.utc)
        session.add(message)
        session.commit()
        return

    lead = session.get(Lead, message.lead_id)
    if not lead:
        logger.error(
            "Cannot process inbound message_id=%s: lead %s not found",
            message.id, message.lead_id,
        )
        message.delivery_status = "inbound_error"
        message.updated_at = datetime.now(timezone.utc)
        session.add(message)
        session.commit()
        return
    if not lead.workspace_id:
        if lead.tenant_id is None:
            logger.error(
                "Cannot process inbound message_id=%s: lead %s has no tenant_id",
                message.id, message.lead_id,
            )
            message.delivery_status = "inbound_error"
            message.updated_at = datetime.now(timezone.utc)
            session.add(message)
            session.commit()
            return
        workspace = get_or_create_default_workspace(session, int(lead.tenant_id))
        lead.workspace_id = workspace.id
        session.add(lead)
        session.commit()
        session.refresh(lead)

    thread_id = getattr(message, "thread_id", None)
    tenant_id = getattr(message, "tenant_id", None)
    if thread_id is not None and tenant_id is not None and hasattr(session, "exec"):
        from routers.ai_crm_helpers import clear_thread_followup_state

        clear_thread_followup_state(
            session=session,
            tenant_id=int(tenant_id),
            thread_id=int(thread_id),
            reason="customer_replied_inbound",
        )
        lead.next_followup_at = None
        session.add(lead)
        session.commit()
        session.refresh(lead)

    history = _build_thread_history(session, message)
    prepared = await _prepare_media_inbound_for_runtime(message)
    if prepared.get("processing"):
        payload = _message_payload(message)
        payload["media_processing"] = prepared["processing"]
        message.raw_payload = payload
        session.add(message)
        session.commit()
        session.refresh(message)

    if not bool(prepared.get("should_run_runtime", True)):
        payload = _message_payload(message)
        payload["inbound_skip_reason"] = prepared.get("skip_reason") or "MEDIA_PROCESSING_REQUIRED"
        payload["inbound_skip_at"] = _iso_now()
        message.raw_payload = payload
        message.delivery_status = "inbound_human_takeover"
        message.updated_at = datetime.now(timezone.utc)
        session.add(message)
        session.commit()
        logger.warning(
            "Skipping AI auto-reply for media-only inbound message_id=%s: %s",
            message.id,
            payload["inbound_skip_reason"],
        )
        return

    logger.info(
        "Running AI agent (id=%s, name=%s) for inbound message_id=%s (lead=%s)",
        agent.id, agent.name, message.id, message.lead_id,
    )
    runtime = ConversationAgentRuntime(session, _get_llm_router())
    runtime_kwargs = _filter_supported_run_turn_kwargs(
        runtime.run_turn,
        {
            "lead_id": message.lead_id,
            "workspace_id": lead.workspace_id,
            "user_message": prepared.get("user_message") or "",
            "agent_id_override": agent.id,
            "thread_id_override": message.thread_id,
            "bypass_safety": True,
            "history_override": history,
            "task_override": prepared.get("task"),
            "llm_extra_params": prepared.get("llm_extra_params"),
        },
    )
    result = await runtime.run_turn(
        **runtime_kwargs,
    )

    status = result.get("status")

    if status == "sent":
        reply_text = result["content"]
        if str(result.get("message_type") or "text").strip().lower() == "audio":
            _enqueue_outbound_reply(
                session=session,
                inbound_message=message,
                agent_id=agent.id,
                text=reply_text,
                message_type="audio",
                extra_raw_payload={
                    "source": "ai_agent_voice_note",
                    **(result.get("raw_payload") or {}),
                },
                ai_trace=result.get("ai_trace"),
                llm_provider=result.get("llm_provider"),
                llm_model=result.get("llm_model"),
                llm_prompt_tokens=result.get("llm_prompt_tokens"),
                llm_completion_tokens=result.get("llm_completion_tokens"),
                llm_total_tokens=result.get("llm_total_tokens"),
                llm_estimated_cost_usd=result.get("llm_estimated_cost_usd"),
            )
        else:
            # Resolve segment delay from the agent's setting (default 800 ms)
            delay_ms = int(getattr(agent, "segment_delay_ms", 800) or 800)
            await _enqueue_segmented_reply(
                session,
                message,
                agent.id,
                reply_text,
                delay_ms=delay_ms,
                ai_trace=result.get("ai_trace"),
                llm_provider=result.get("llm_provider"),
                llm_model=result.get("llm_model"),
                llm_prompt_tokens=result.get("llm_prompt_tokens"),
                llm_completion_tokens=result.get("llm_completion_tokens"),
                llm_total_tokens=result.get("llm_total_tokens"),
                llm_estimated_cost_usd=result.get("llm_estimated_cost_usd"),
            )
            planned_materials = await _plan_sales_material_sends(
                session=session,
                inbound_message=message,
                agent=agent,
                user_message=prepared.get("user_message") or "",
                reply_text=reply_text,
            )
            for planned in planned_materials:
                _enqueue_sales_material_reply(
                    session=session,
                    inbound_message=message,
                    agent_id=agent.id,
                    material=planned["material"],
                    planner_trace=planned.get("planner_trace"),
                )
        message.delivery_status = "inbound_ai_replied"
        logger.info(
            "AI reply enqueued for message_id=%s: %.80s…", message.id, reply_text
        )

    elif status == "blocked":
        reason = result.get("reason", "unknown")
        logger.warning(
            "AI reply blocked by policy for message_id=%s: %s", message.id, reason
        )
        message.delivery_status = "inbound_human_takeover"

    else:
        raise RuntimeError(
            f"ConversationAgentRuntime returned unexpected status '{status}' "
            f"for message_id={message.id}: {result}"
        )

    message.updated_at = datetime.now(timezone.utc)
    session.add(message)
    session.commit()
def _open_inbound_listen_connection():
    return open_inbound_listen_connection(
        engine=_get_engine(),
        inbound_notify_channel=INBOUND_NOTIFY_CHANNEL,
        mark_worker_state=_mark_worker_state,
        iso_now=_iso_now,
        logger=logger,
    )
def _wait_for_inbound_notify(listen_conn, timeout_seconds: float) -> List[int]:
    return wait_for_inbound_notify(
        listen_conn,
        timeout_seconds,
        mark_worker_state=_mark_worker_state,
        worker_state=INBOUND_WORKER_STATE,
        iso_now=_iso_now,
        logger=logger,
    )
def _claim_inbound_message(session: Session, message_id: int) -> Optional[Any]:
    UnifiedMessage, _, _, _, _, _ = _get_db_models()
    if _get_engine().dialect.name == "postgresql":
        row = session.connection().execute(
            text(
                """
                UPDATE et_messages
                SET delivery_status = 'inbound_processing',
                    updated_at = NOW()
                WHERE id = :message_id
                  AND direction = 'inbound'
                  AND delivery_status = 'received'
                  AND thread_id IS NOT NULL
                RETURNING id
                """
            ),
            {"message_id": message_id},
        ).first()
        if not row:
            session.rollback()
            return None
        session.commit()
        if isinstance(row, (tuple, list)):
            claimed_raw = row[0]
        elif hasattr(row, "_mapping"):
            claimed_raw = next(iter(row._mapping.values()))
        else:
            claimed_raw = row
        claimed_id = int(claimed_raw)
        _mark_worker_state(
            last_claimed_at=_iso_now(),
            last_claimed_message_id=claimed_id,
            claimed_total=INBOUND_WORKER_STATE.get("claimed_total", 0) + 1,
        )
        return session.get(UnifiedMessage, claimed_id)

    message = session.get(UnifiedMessage, message_id)
    if (
        not message
        or message.direction != "inbound"
        or message.delivery_status != "received"
        or message.thread_id is None
    ):
        return None
    message.delivery_status = "inbound_processing"
    message.updated_at = datetime.now(timezone.utc)
    session.add(message)
    session.commit()
    session.refresh(message)
    _mark_worker_state(
        last_claimed_at=_iso_now(),
        last_claimed_message_id=message.id,
        claimed_total=INBOUND_WORKER_STATE.get("claimed_total", 0) + 1,
    )
    return message
def _mark_inbound_error(session: Session, message_id: int, reason: Optional[str] = None):
    UnifiedMessage, _, _, _, _, _ = _get_db_models()
    db_inbound = session.get(UnifiedMessage, message_id)
    if db_inbound:
        db_inbound.delivery_status = "inbound_error"
        db_inbound.updated_at = datetime.now(timezone.utc)
        payload = dict(db_inbound.raw_payload or {})
        if reason:
            payload["inbound_error_reason"] = str(reason)[:1000]
            payload["inbound_error_at"] = _iso_now()
        db_inbound.raw_payload = payload
        session.add(db_inbound)
        session.commit()
    if reason:
        _mark_worker_state(
            last_error_at=_iso_now(),
            last_error_message=f"message_id={message_id}: {reason}",
            errors_total=INBOUND_WORKER_STATE.get("errors_total", 0) + 1,
        )
    else:
        _mark_worker_state(
            last_error_at=_iso_now(),
            last_error_message=f"inbound_error state set for message_id={message_id}",
            errors_total=INBOUND_WORKER_STATE.get("errors_total", 0) + 1,
        )
async def background_inbound_worker_loop():
    UnifiedMessage, _, _, _, _, _ = _get_db_models()
    logger.info(
        "Starting inbound worker loop (poll=%ss, batch=%s)",
        INBOUND_POLL_SECONDS,
        INBOUND_BATCH_SIZE,
    )
    _mark_worker_state(started_at=_iso_now())
    listen_conn = None
    engine = _get_engine()
    if engine.dialect.name == "postgresql":
        try:
            listen_conn = _open_inbound_listen_connection()
        except Exception as exc:
            logger.warning("Inbound LISTEN disabled (connect failed): %s", exc)
            listen_conn = None

    while True:
        _mark_worker_state(last_loop_at=_iso_now())
        processed = 0
        try:
            with Session(engine) as session:
                notified_ids: List[int] = []
                if listen_conn is not None:
                    notified_ids = await asyncio.to_thread(
                        _wait_for_inbound_notify,
                        listen_conn,
                        INBOUND_POLL_SECONDS,
                    )

                for message_id in list(dict.fromkeys(notified_ids)):
                    if processed >= INBOUND_BATCH_SIZE:
                        break
                    claimed = _claim_inbound_message(session, message_id)
                    if not claimed:
                        continue
                    try:
                        await _process_one_inbound(session, claimed)
                        processed += 1
                        _mark_worker_state(
                            last_processed_at=_iso_now(),
                            last_processed_message_id=message_id,
                            processed_total=INBOUND_WORKER_STATE.get("processed_total", 0) + 1,
                        )
                    except Exception as exc:
                        logger.exception(
                            "Inbound processing error for message_id=%s: %s",
                            message_id, exc,
                        )
                        _mark_worker_state(
                            last_error_at=_iso_now(),
                            last_error_message=f"message_id={message_id}: {exc}",
                            errors_total=INBOUND_WORKER_STATE.get("errors_total", 0) + 1,
                        )
                        session.rollback()
                        _mark_inbound_error(session, message_id, reason=str(exc))

                remaining = max(INBOUND_BATCH_SIZE - processed, 0)
                if remaining > 0:
                    inbound_batch = session.exec(
                        select(UnifiedMessage)
                        .where(
                            UnifiedMessage.direction == "inbound",
                            UnifiedMessage.delivery_status == "received",
                            UnifiedMessage.thread_id.is_not(None),
                        )
                        .order_by(UnifiedMessage.created_at.asc(), UnifiedMessage.id.asc())
                        .limit(remaining)
                    ).all()

                    for inbound in inbound_batch:
                        claimed = _claim_inbound_message(session, inbound.id)
                        if not claimed:
                            continue
                        try:
                            await _process_one_inbound(session, claimed)
                            processed += 1
                            _mark_worker_state(
                                last_processed_at=_iso_now(),
                                last_processed_message_id=inbound.id,
                                processed_total=INBOUND_WORKER_STATE.get("processed_total", 0) + 1,
                            )
                        except Exception as exc:
                            logger.exception(
                                "Inbound processing error for message_id=%s: %s",
                                inbound.id, exc,
                            )
                            _mark_worker_state(
                                last_error_at=_iso_now(),
                                last_error_message=f"message_id={inbound.id}: {exc}",
                                errors_total=INBOUND_WORKER_STATE.get("errors_total", 0) + 1,
                            )
                            session.rollback()
                            _mark_inbound_error(session, inbound.id, reason=str(exc))

        except Exception as exc:
            logger.exception("Inbound worker loop error: %s", exc)
            _mark_worker_state(
                last_error_at=_iso_now(),
                last_error_message=f"loop_error: {exc}",
                errors_total=INBOUND_WORKER_STATE.get("errors_total", 0) + 1,
            )
            if listen_conn is not None:
                try:
                    listen_conn.close()
                except Exception:
                    pass
                listen_conn = None
            if _get_engine().dialect.name == "postgresql":
                try:
                    listen_conn = _open_inbound_listen_connection()
                except Exception as reconnect_exc:
                    logger.warning("Inbound LISTEN reconnect failed: %s", reconnect_exc)

        if processed == 0 and listen_conn is None:
            await asyncio.sleep(INBOUND_POLL_SECONDS)
        else:
            await asyncio.sleep(0)
