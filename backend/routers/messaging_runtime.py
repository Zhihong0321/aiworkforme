"""
MODULE: Messaging Runtime Helpers
PURPOSE: Shared outbound/LLM runtime operations used by messaging route modules.
DOES: Generate outreach content and dispatch queued outbound messages.
DOES NOT: Register HTTP routes directly.
INVARIANTS: Queue status transitions and provider payload semantics stay stable.
SAFE CHANGE: Keep side effects equivalent when extracting logic.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import logging

import httpx
from fastapi import HTTPException
from sqlmodel import Session, select

from src.adapters.db.agent_models import Agent
from src.adapters.db.channel_models import ChannelSession, SessionStatus
from src.adapters.db.crm_models import Lead
from src.adapters.db.messaging_models import OutboundQueue, UnifiedMessage
from src.infra.llm.costs import estimate_llm_cost_usd
from src.infra.llm.router import LLMRouter
from src.infra.llm.schemas import LLMTask

from .messaging_helpers import (
    channel_send_url as _channel_send_url,
    extract_whatsapp_recipient as _extract_whatsapp_recipient,
    mark_retry as _mark_retry,
    normalize_usage as _normalize_usage,
    provider_headers as _provider_headers,
    resolve_whatsapp_base_url as _resolve_whatsapp_base_url,
)
from .messaging_schemas import DispatchResponse

logger = logging.getLogger(__name__)


async def generate_initial_outreach_text(
    router: LLMRouter, agent: Agent, lead: Lead, include_context_prompt: bool
) -> Tuple[str, Dict[str, Any]]:
    lead_name = lead.name or "there"
    prompt = (
        "Generate one short first outreach WhatsApp message for this lead. "
        "Keep it natural, polite, and action-oriented. No markdown."
        f"\nLead name: {lead_name}\nLead contact id: {lead.external_id}"
    )
    try:
        response = await router.execute(
            task=LLMTask.CONVERSATION,
            messages=[
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=220,
            model=getattr(agent, "model", None),
        )
        text = (response.content or "").strip()
        if text:
            provider_info = response.provider_info or {}
            ai_trace = {
                "schema_version": "1.0",
                "task": LLMTask.CONVERSATION.value,
                "provider": provider_info.get("provider") or "unknown",
                "model": provider_info.get("model") or "unknown",
                "usage": _normalize_usage(response.usage or {}),
                "context_prompt": agent.system_prompt if include_context_prompt else None,
                "recorded_at": datetime.utcnow().isoformat(),
            }
            usage = ai_trace["usage"]
            ai_trace["usage"]["estimated_cost_usd"] = estimate_llm_cost_usd(
                ai_trace["provider"],
                ai_trace["model"],
                usage.get("prompt_tokens", 0) or 0,
                usage.get("completion_tokens", 0) or 0,
            )
            return text, ai_trace
    except Exception as exc:
        logger.warning("Initial outreach generation failed for lead_id=%s: %s", lead.id, exc)
    return (
        f"Hi {lead_name}, I wanted to follow up and see how I can help you today.",
        {
            "schema_version": "1.0",
            "task": LLMTask.CONVERSATION.value,
            "provider": "fallback_template",
            "model": "none",
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "raw_usage": {},
                "estimated_cost_usd": 0,
            },
            "context_prompt": agent.system_prompt if include_context_prompt else None,
            "recorded_at": datetime.utcnow().isoformat(),
        },
    )


def send_whatsapp_message(session: Session, message: UnifiedMessage) -> str:
    if not message.channel_session_id:
        raise RuntimeError("WhatsApp outbound requires channel_session_id")

    channel_session = session.get(ChannelSession, message.channel_session_id)
    if not channel_session or channel_session.tenant_id != message.tenant_id:
        raise RuntimeError("Invalid WhatsApp channel session")
    channel_type = (
        channel_session.channel_type.value
        if hasattr(channel_session.channel_type, "value")
        else str(channel_session.channel_type)
    )
    if channel_type != "whatsapp":
        raise RuntimeError("channel_session_id is not a WhatsApp session")
    if channel_session.status != SessionStatus.ACTIVE:
        raise RuntimeError("WhatsApp session is not active")

    lead = session.get(Lead, message.lead_id)
    if not lead or lead.tenant_id != message.tenant_id:
        raise RuntimeError("Lead not found for outbound message")

    base_url = _resolve_whatsapp_base_url(channel_session)
    endpoint = f"{base_url}/messages/send"
    payload = {
        "sessionId": channel_session.session_identifier,
        "to": _extract_whatsapp_recipient(lead.external_id),
        "text": message.text_content or "",
    }

    with httpx.Client(timeout=20.0) as client:
        resp = client.post(endpoint, headers=_provider_headers(), json=payload)
        resp.raise_for_status()
        body = resp.json() if resp.content else {}

    result = body.get("result") or {}
    key = result.get("key") if isinstance(result, dict) else {}
    provider_message_id = (
        body.get("provider_message_id")
        or body.get("message_id")
        or (key.get("id") if isinstance(key, dict) else None)
        or message.external_message_id
    )
    return str(provider_message_id)


def send_to_channel(session: Session, message: UnifiedMessage) -> str:
    if message.channel == "whatsapp":
        return send_whatsapp_message(session, message)

    send_url = _channel_send_url(message.channel)
    if not send_url:
        raise RuntimeError(f"Missing send URL for channel: {message.channel}")

    payload = {
        "tenant_id": message.tenant_id,
        "lead_id": message.lead_id,
        "message_id": message.id,
        "external_message_id": message.external_message_id,
        "channel_session_id": message.channel_session_id,
        "message_type": message.message_type,
        "text_content": message.text_content,
        "media_url": message.media_url,
    }

    with httpx.Client(timeout=15.0) as client:
        resp = client.post(send_url, json=payload)
        resp.raise_for_status()
        body = resp.json() if resp.content else {}
    provider_message_id = body.get("provider_message_id") or body.get("message_id") or message.external_message_id
    return str(provider_message_id)


def dispatch_next_outbound_for_tenant(session: Session, tenant_id: int) -> Optional[DispatchResponse]:
    now = datetime.utcnow()
    queue = session.exec(
        select(OutboundQueue)
        .where(
            OutboundQueue.tenant_id == tenant_id,
            OutboundQueue.status == "queued",
            OutboundQueue.next_attempt_at <= now,
        )
        .order_by(OutboundQueue.next_attempt_at.asc(), OutboundQueue.id.asc())
    ).first()

    if not queue:
        return None

    message = session.get(UnifiedMessage, queue.message_id)
    if not message or message.tenant_id != tenant_id:
        queue.status = "failed"
        queue.last_error = "Message not found or tenant mismatch"
        queue.updated_at = now
        session.add(queue)
        session.commit()
        raise HTTPException(status_code=409, detail="Queue item is invalid")

    queue.status = "dispatching"
    queue.updated_at = now
    message.delivery_status = "dispatching"
    message.updated_at = now
    session.add(queue)
    session.add(message)
    session.commit()

    try:
        provider_message_id = send_to_channel(session, message)
        if message.channel == "whatsapp":
            queue.status = "accepted"
            message.delivery_status = "provider_accepted"
        else:
            queue.status = "sent"
            message.delivery_status = "sent"
        queue.updated_at = datetime.utcnow()
        queue.last_error = None

        message.updated_at = datetime.utcnow()
        merged_payload = dict(message.raw_payload or {})
        merged_payload["provider_message_id"] = provider_message_id
        if message.channel == "whatsapp":
            merged_payload["provider_status"] = "pending"
        message.raw_payload = merged_payload

        session.add(queue)
        session.add(message)
        session.commit()

        result = DispatchResponse(
            queue_id=queue.id,
            message_id=message.id,
            channel=message.channel,
            status=queue.status,
            retry_count=queue.retry_count,
        )
        logger.info(
            "Outbound dispatched: tenant_id=%s queue_id=%s message_id=%s channel=%s",
            tenant_id,
            queue.id,
            message.id,
            message.channel,
        )
        return result
    except Exception as exc:
        _mark_retry(queue, message, str(exc))
        session.add(queue)
        session.add(message)
        session.commit()
        logger.warning(
            "Outbound dispatch failed: tenant_id=%s queue_id=%s message_id=%s retry=%s error=%s",
            tenant_id,
            queue.id,
            message.id,
            queue.retry_count,
            str(exc),
        )
        return DispatchResponse(
            queue_id=queue.id,
            message_id=message.id,
            channel=message.channel,
            status=queue.status,
            retry_count=queue.retry_count,
            detail=str(exc),
        )


def list_tenant_ids_with_queued_outbound(session: Session) -> List[int]:
    """Return tenant IDs that currently have queued outbound items."""
    return session.exec(
        select(OutboundQueue.tenant_id)
        .where(OutboundQueue.status == "queued")
        .distinct()
    ).all()
