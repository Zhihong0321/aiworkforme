"""
MODULE: Messaging WhatsApp Import Routes
PURPOSE: Dedicated endpoint module for WhatsApp conversation import workflow.
DOES: Handle chat/message import command and related persistence orchestration.
DOES NOT: Manage WhatsApp session connect/refresh lifecycle endpoints.
INVARIANTS: Import endpoint path and behavior remain unchanged.
SAFE CHANGE: Keep provider request semantics and error mapping stable.
"""

import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from src.adapters.api.dependencies import AuthContext, require_tenant_access
from src.adapters.db.crm_models import Lead, Workspace
from src.adapters.db.messaging_models import UnifiedMessage
from src.infra.database import get_session

from .messaging_helpers import (
    chat_display_name as _chat_display_name,
    chat_jid as _chat_jid,
    chat_phone_number as _chat_phone_number,
    extract_list as _extract_list,
    get_or_create_thread as _get_or_create_thread,
    message_direction as _message_direction,
    message_external_id as _message_external_id,
    message_raw_payload as _message_raw_payload,
    message_text as _message_text,
    message_timestamp as _message_timestamp,
    message_type as _message_type,
    name_confidence_score as _name_confidence_score,
    normalize_seed_phone as _normalize_seed_phone,
    normalize_whatsapp_external_id_from_jid as _normalize_whatsapp_external_id_from_jid,
    phone_match_keys as _phone_match_keys,
    provider_headers as _provider_headers,
    resolve_whatsapp_base_url as _resolve_whatsapp_base_url,
    resolve_whatsapp_channel_session_for_tenant as _resolve_whatsapp_channel_session_for_tenant,
)
from .messaging_schemas import WhatsAppConversationImportRequest, WhatsAppConversationImportResponse

router = APIRouter()

@router.post(
    "/workspaces/{workspace_id}/import-whatsapp-conversations",
    response_model=WhatsAppConversationImportResponse,
)
def import_whatsapp_conversations(
    workspace_id: int,
    payload: WhatsAppConversationImportRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    raise HTTPException(
        status_code=410,
        detail="WhatsApp lead import is disabled because provider chat history sync is unreliable.",
    )

    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")

    chat_limit = max(1, min(int(payload.chat_limit or 200), 500))
    message_limit = max(1, min(int(payload.message_limit_per_chat or 100), 500))
    channel_session = _resolve_whatsapp_channel_session_for_tenant(
        session=session,
        tenant_id=auth.tenant.id,
        channel_session_id=payload.channel_session_id,
    )
    base_url = _resolve_whatsapp_base_url(channel_session)

    existing_leads = session.exec(
        select(Lead).where(
            Lead.tenant_id == auth.tenant.id,
            Lead.workspace_id == workspace_id,
        )
    ).all()
    leads_by_external: Dict[str, Lead] = {}
    leads_by_digits: Dict[str, Lead] = {}
    leads_by_phone_key: Dict[str, Lead] = {}

    def _index_lead(lead: Lead):
        external = (lead.external_id or "").strip()
        if external:
            leads_by_external[external] = lead
            digits = re.sub(r"\D+", "", external)
            if digits:
                leads_by_digits[digits] = lead
            for key in _phone_match_keys(external):
                leads_by_phone_key[key] = lead
        if lead.whatsapp_lid:
            leads_by_phone_key[lead.whatsapp_lid] = lead

    for lead in existing_leads:
        _index_lead(lead)

    errors: List[str] = []
    chats_scanned = 0
    chats_imported = 0
    leads_created = 0
    threads_touched: set[int] = set()
    messages_created = 0
    messages_skipped_existing = 0
    lead_names_updated = 0
    skipped_group_chats = 0

    try:
        with httpx.Client(timeout=30.0) as client:
            seed_phone = _normalize_seed_phone(payload.seed_phone)
            if payload.seed_phone is not None and not seed_phone:
                raise HTTPException(
                    status_code=400,
                    detail="seed_phone must contain digits with country code (example: 60123456789)",
                )
            if seed_phone:
                seed_lead = (
                    leads_by_external.get(seed_phone)
                    or leads_by_digits.get(seed_phone)
                    or next((leads_by_phone_key.get(k) for k in _phone_match_keys(seed_phone) if leads_by_phone_key.get(k)), None)
                )
                if not seed_lead:
                    seed_lead = Lead(
                        tenant_id=auth.tenant.id,
                        workspace_id=workspace_id,
                        external_id=seed_phone,
                        name=None,
                        stage="CONTACTED",
                        tags=[],
                        is_whatsapp_valid=bool(8 <= len(seed_phone) <= 15),
                        created_at=datetime.utcnow(),
                    )
                    session.add(seed_lead)
                    session.commit()
                    session.refresh(seed_lead)
                    leads_created += 1
                    _index_lead(seed_lead)

                seed_text = (payload.seed_text or "").strip() or "Hi, this is a test message to initialize chat import."
                seed_res = client.post(
                    f"{base_url}/messages/send",
                    headers=_provider_headers(),
                    json={
                        "sessionId": channel_session.session_identifier,
                        "to": seed_phone,
                        "text": seed_text,
                    },
                )
                try:
                    seed_res.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    detail = ""
                    try:
                        detail = str(seed_res.json())
                    except Exception:
                        detail = seed_res.text or str(exc)
                    raise HTTPException(
                        status_code=502,
                        detail=f"Seed message failed for {seed_phone}: {detail[:400]}",
                    ) from exc
                # Allow provider cache to include the fresh chat before listing chats.
                time.sleep(1.2)

            chats_res = client.get(
                f"{base_url}/chats",
                headers=_provider_headers(),
                params={"sessionId": channel_session.session_identifier, "limit": chat_limit},
            )
            chats_res.raise_for_status()
            chats_body = chats_res.json() if chats_res.content else {}
            chats = _extract_list(chats_body, "chats")

            for chat in chats:
                chats_scanned += 1
                jid = _chat_jid(chat)
                if not jid:
                    errors.append(f"Skipped chat with missing jid at index {chats_scanned}.")
                    continue
                is_group_chat = bool(chat.get("isGroup")) or jid.endswith("@g.us")
                if (not payload.include_group_chats) and is_group_chat:
                    skipped_group_chats += 1
                    continue

                is_lid_chat = jid.endswith("@lid")
                phone_number = _chat_phone_number(chat)
                external_id = phone_number
                if not external_id:
                    if jid.endswith("@s.whatsapp.net"):
                        external_id = _normalize_whatsapp_external_id_from_jid(jid)
                    else:
                        external_id = jid
                if not external_id:
                    errors.append(f"Skipped chat {jid}: cannot derive external_id.")
                    continue
                digits = re.sub(r"\D+", "", external_id)
                display_name = _chat_display_name(chat, jid)

                lead: Optional[Lead] = None
                if is_lid_chat:
                    lead = session.exec(
                        select(Lead).where(
                            Lead.tenant_id == auth.tenant.id,
                            Lead.workspace_id == workspace_id,
                            Lead.whatsapp_lid == jid,
                        )
                    ).first()
                if not lead:
                    lead = leads_by_external.get(external_id) or leads_by_digits.get(digits)
                if not lead:
                    for key in _phone_match_keys(external_id):
                        existing = leads_by_phone_key.get(key)
                        if existing:
                            lead = existing
                            break
                if not lead:
                    lead = Lead(
                        tenant_id=auth.tenant.id,
                        workspace_id=workspace_id,
                        external_id=external_id,
                        whatsapp_lid=jid if is_lid_chat else None,
                        name=display_name if display_name != jid else None,
                        stage="CONTACTED",
                        tags=[],
                        is_whatsapp_valid=bool(8 <= len(digits) <= 15),
                        created_at=datetime.utcnow(),
                    )
                    session.add(lead)
                    session.commit()
                    session.refresh(lead)
                    _index_lead(lead)
                    leads_created += 1
                elif display_name and display_name != jid:
                    existing_name = (lead.name or "").strip()
                    existing_score = _name_confidence_score(existing_name, lead.external_id, jid)
                    incoming_score = _name_confidence_score(display_name, lead.external_id, jid)
                    # Update only when existing name is empty/weak and imported value looks stronger.
                    if incoming_score >= 3 and incoming_score > existing_score:
                        lead.name = display_name
                        if is_lid_chat and not lead.whatsapp_lid:
                            lead.whatsapp_lid = jid
                        session.add(lead)
                        session.commit()
                        session.refresh(lead)
                        _index_lead(lead)
                        lead_names_updated += 1
                elif is_lid_chat and not lead.whatsapp_lid:
                    lead.whatsapp_lid = jid
                    session.add(lead)
                    session.commit()
                    session.refresh(lead)
                    _index_lead(lead)

                thread = _get_or_create_thread(session, auth.tenant.id, lead.id, "whatsapp")
                if thread.id is not None:
                    threads_touched.add(thread.id)

                try:
                    msg_res = client.get(
                        f"{base_url}/chats/{quote(jid, safe='')}/messages",
                        headers=_provider_headers(),
                        params={
                            "sessionId": channel_session.session_identifier,
                            "limit": message_limit,
                        },
                    )
                    msg_res.raise_for_status()
                    msg_body = msg_res.json() if msg_res.content else {}
                except Exception as exc:
                    errors.append(f"Failed messages fetch for {jid}: {str(exc)}")
                    continue

                raw_messages = _extract_list(msg_body, "messages")
                if not raw_messages:
                    chats_imported += 1
                    continue

                indexed_messages: List[Tuple[datetime, int, Dict[str, Any], str]] = []
                for idx, message in enumerate(raw_messages):
                    external_message_id = _message_external_id(message)
                    if not external_message_id:
                        fallback_ts = int(_message_timestamp(message).timestamp())
                        external_message_id = f"import_{jid}_{fallback_ts}_{idx}"
                    indexed_messages.append((_message_timestamp(message), idx, message, external_message_id))

                external_ids = list({item[3] for item in indexed_messages})
                existing_ids = set(
                    session.exec(
                        select(UnifiedMessage.external_message_id).where(
                            UnifiedMessage.tenant_id == auth.tenant.id,
                            UnifiedMessage.channel == "whatsapp",
                            UnifiedMessage.external_message_id.in_(external_ids),
                        )
                    ).all()
                )

                for created_at, _, message, external_message_id in sorted(
                    indexed_messages, key=lambda item: (item[0], item[1])
                ):
                    if external_message_id in existing_ids:
                        messages_skipped_existing += 1
                        continue
                    direction = _message_direction(message)
                    text_content = _message_text(message)
                    message_type = _message_type(message)
                    imported = UnifiedMessage(
                        tenant_id=auth.tenant.id,
                        lead_id=lead.id,
                        thread_id=thread.id,
                        channel_session_id=channel_session.id,
                        channel="whatsapp",
                        external_message_id=external_message_id,
                        direction=direction,
                        message_type=message_type,
                        text_content=text_content,
                        raw_payload={
                            "source": "baileys_import",
                            "chat": chat,
                            "message": _message_raw_payload(message),
                        },
                        delivery_status="sent" if direction == "outbound" else "received",
                        created_at=created_at,
                        updated_at=datetime.utcnow(),
                    )
                    session.add(imported)
                    existing_ids.add(external_message_id)
                    messages_created += 1

                thread.updated_at = datetime.utcnow()
                session.add(thread)
                session.commit()
                chats_imported += 1
    except httpx.HTTPStatusError as exc:
        body_detail = ""
        try:
            parsed = exc.response.json()
            body_detail = parsed.get("error") or parsed.get("detail") or str(parsed)
        except Exception:
            body_detail = (exc.response.text or "").strip()
        if body_detail:
            body_detail = f" - {body_detail[:400]}"
        raise HTTPException(
            status_code=502,
            detail=f"WhatsApp import failed (provider status {exc.response.status_code}){body_detail}",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"WhatsApp import failed: {exc}") from exc

    return WhatsAppConversationImportResponse(
        workspace_id=workspace_id,
        channel_session_id=channel_session.id or 0,
        chats_scanned=chats_scanned,
        chats_imported=chats_imported,
        leads_created=leads_created,
        threads_touched=len(threads_touched),
        messages_created=messages_created,
        messages_skipped_existing=messages_skipped_existing,
        lead_names_updated=lead_names_updated,
        skipped_group_chats=skipped_group_chats,
        errors=errors[:30],
    )
