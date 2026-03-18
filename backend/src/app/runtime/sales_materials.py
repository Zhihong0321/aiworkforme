"""
Managed storage and thread-state helpers for agent sales materials.
"""

from __future__ import annotations

import os
import re
from ipaddress import ip_address
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse, unquote
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from src.adapters.db.agent_models import AgentSalesMaterial

SALES_MATERIALS_DIR = Path(
    os.getenv("SALES_MATERIALS_DIR")
    or (Path(__file__).resolve().parents[3] / "storage" / "sales-materials")
)
SALES_MATERIALS_DIR.mkdir(parents=True, exist_ok=True)

SALES_MATERIAL_MAX_BYTES = 30 * 1024 * 1024

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
ALLOWED_DOC_TYPES = {
    "application/pdf": ".pdf",
}
ALLOWED_TYPES = {**ALLOWED_IMAGE_TYPES, **ALLOWED_DOC_TYPES}


def _slugify_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", (value or "").strip())
    cleaned = cleaned.strip(".-_") or "material"
    return cleaned[:120]


def sales_material_kind(media_type: str) -> str:
    return "image" if str(media_type or "").startswith("image/") else "document"


def is_supported_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _host_is_probably_local(host: str) -> bool:
    normalized = str(host or "").strip().lower().strip("[]")
    if not normalized:
        return True
    if normalized in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return True
    if normalized.endswith(".local"):
        return True
    try:
        parsed_ip = ip_address(normalized)
    except ValueError:
        return False
    return bool(
        parsed_ip.is_private
        or parsed_ip.is_loopback
        or parsed_ip.is_link_local
        or parsed_ip.is_unspecified
        or parsed_ip.is_reserved
    )


def is_public_http_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    return not _host_is_probably_local(parsed.hostname or "")


def is_youtube_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip())
    host = (parsed.netloc or "").lower()
    return host.endswith("youtube.com") or host.endswith("youtu.be")


def sales_material_kind_for_material(material: AgentSalesMaterial) -> str:
    source_type = str(getattr(material, "source_type", "file") or "file").strip().lower()
    if source_type == "url":
        return "youtube" if is_youtube_url(getattr(material, "external_url", "") or getattr(material, "public_url", "")) else "link"
    return sales_material_kind(getattr(material, "media_type", ""))


def detect_sales_material_type(filename: str, content_type: str, content: bytes) -> str:
    normalized_type = str(content_type or "").split(";")[0].strip().lower()
    suffix = Path(filename or "").suffix.lower()

    if normalized_type in ALLOWED_TYPES:
        return normalized_type

    if suffix == ".pdf" or content[:4] == b"%PDF":
        return "application/pdf"

    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"

    raise HTTPException(status_code=400, detail="Only PDF and image files are allowed")


def validate_sales_material_upload(filename: str, content_type: str, content: bytes) -> Dict[str, Any]:
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    media_type = detect_sales_material_type(filename, content_type, content)
    size_limit = SALES_MATERIAL_MAX_BYTES
    if len(content) > size_limit:
        label = "image" if media_type.startswith("image/") else "PDF"
        raise HTTPException(
            status_code=400,
            detail=f"{label} exceeds upload limit of {size_limit // (1024 * 1024)}MB",
        )

    default_ext = ALLOWED_TYPES.get(media_type, "")
    suffix = Path(filename or "").suffix.lower() or default_ext
    if not suffix:
        suffix = default_ext or ".bin"

    sanitized_name = _slugify_filename(Path(filename or f"material{suffix}").name)
    if not Path(sanitized_name).suffix:
        sanitized_name = f"{sanitized_name}{suffix}"

    return {
        "filename": sanitized_name,
        "media_type": media_type,
        "source_type": "file",
        "external_url": "",
        "file_size_bytes": len(content),
        "suffix": suffix,
        "kind": sales_material_kind(media_type),
    }


def build_url_sales_material(url: str, description: str) -> Dict[str, Any]:
    normalized_url = str(url or "").strip()
    if not is_supported_url(normalized_url):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    parsed = urlparse(normalized_url)
    host = (parsed.netloc or "link").lower()
    path_name = Path(unquote(parsed.path or "")).name.strip()
    if path_name:
        title = path_name
    elif is_youtube_url(normalized_url):
        title = "youtube-link"
    else:
        title = host.replace(".", "-") or "link"

    filename = _slugify_filename(title)
    if is_youtube_url(normalized_url) and not filename.endswith(".url"):
        filename = f"{filename}.url"
    elif "." not in filename:
        filename = f"{filename}.url"

    return {
        "filename": filename,
        "media_type": "text/uri-list",
        "source_type": "url",
        "external_url": normalized_url,
        "file_size_bytes": len(normalized_url.encode("utf-8")),
        "suffix": "",
        "kind": "youtube" if is_youtube_url(normalized_url) else "link",
        "description": str(description or "").strip(),
    }


def build_public_base_url(request: Optional[Any] = None) -> str:
    base = (os.getenv("APP_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if base:
        parsed = urlparse(base)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return base
    if request is not None:
        return str(request.base_url).rstrip("/")
    return "http://127.0.0.1:8080"


def build_sales_material_public_url(public_token: str, request: Optional[Any] = None) -> str:
    return f"{build_public_base_url(request)}/api/v1/public/sales-materials/{public_token}"


def resolve_sales_material_public_url(
    material: AgentSalesMaterial,
    request: Optional[Any] = None,
) -> str:
    source_type = str(getattr(material, "source_type", "file") or "file").strip().lower()
    if source_type == "url":
        return str(getattr(material, "external_url", "") or getattr(material, "public_url", "") or "").strip()

    public_token = str(getattr(material, "public_token", "") or "").strip()
    stored_url = str(getattr(material, "public_url", "") or "").strip()

    configured_base = (os.getenv("APP_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if public_token and configured_base:
        parsed = urlparse(configured_base)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return build_sales_material_public_url(public_token, request=request)

    if request is not None and public_token:
        return build_sales_material_public_url(public_token, request=request)

    if stored_url and is_supported_url(stored_url):
        return stored_url

    if public_token:
        return build_sales_material_public_url(public_token, request=request)

    return stored_url


def build_sales_material_stored_name(filename: str, suffix: str, public_token: Optional[str] = None) -> str:
    token = public_token or uuid4().hex
    stem = _slugify_filename(Path(filename).stem)
    return f"{token}-{stem}{suffix}"


def agent_sales_material_dir(tenant_id: int, agent_id: int) -> Path:
    path = SALES_MATERIALS_DIR / f"tenant-{tenant_id}" / f"agent-{agent_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sales_material_path(material: AgentSalesMaterial) -> Path:
    tenant_id = int(material.tenant_id or 0)
    return agent_sales_material_dir(tenant_id, material.agent_id) / material.stored_name


def write_sales_material_file(material: AgentSalesMaterial, content: bytes) -> None:
    if str(getattr(material, "source_type", "file") or "file").strip().lower() != "file":
        return
    sales_material_path(material).write_bytes(content)


def delete_sales_material_file(material: AgentSalesMaterial) -> None:
    if str(getattr(material, "source_type", "file") or "file").strip().lower() != "file":
        return
    try:
        sales_material_path(material).unlink(missing_ok=True)
    except Exception:
        pass


def serialize_sales_material(material: AgentSalesMaterial) -> Dict[str, Any]:
    source_type = str(getattr(material, "source_type", "file") or "file").strip().lower()
    resolved_url = resolve_sales_material_public_url(material)
    return {
        "id": material.id,
        "agent_id": material.agent_id,
        "filename": material.filename,
        "media_type": material.media_type,
        "kind": sales_material_kind_for_material(material),
        "source_type": source_type,
        "external_url": (material.external_url or "").strip() or None,
        "file_size_bytes": material.file_size_bytes,
        "description": material.description,
        "public_url": resolved_url,
        "created_at": material.created_at.isoformat() if material.created_at else None,
        "updated_at": material.updated_at.isoformat() if material.updated_at else None,
    }


def list_agent_sales_materials(session: Session, tenant_id: int, agent_id: int) -> List[AgentSalesMaterial]:
    return session.exec(
        select(AgentSalesMaterial)
        .where(
            AgentSalesMaterial.tenant_id == tenant_id,
            AgentSalesMaterial.agent_id == agent_id,
        )
        .order_by(AgentSalesMaterial.created_at.desc(), AgentSalesMaterial.id.desc())
    ).all()


def get_sales_material_by_public_token(session: Session, public_token: str) -> Optional[AgentSalesMaterial]:
    return session.exec(
        select(AgentSalesMaterial).where(AgentSalesMaterial.public_token == public_token)
    ).first()


def thread_sales_material_state(session: Session, tenant_id: int, thread_id: Optional[int]) -> Dict[int, Dict[str, Any]]:
    if not thread_id:
        return {}

    UnifiedMessage = __import__(
        "src.adapters.db.messaging_models",
        fromlist=["UnifiedMessage"],
    ).UnifiedMessage

    rows = session.exec(
        select(UnifiedMessage)
        .where(
            UnifiedMessage.tenant_id == tenant_id,
            UnifiedMessage.thread_id == thread_id,
            UnifiedMessage.direction == "outbound",
        )
        .order_by(UnifiedMessage.created_at.asc(), UnifiedMessage.id.asc())
    ).all()

    state: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        payload = row.raw_payload if isinstance(row.raw_payload, dict) else {}
        material_ids: List[int] = []
        single_id = payload.get("sales_material_id")
        if isinstance(single_id, int):
            material_ids.append(single_id)
        elif isinstance(single_id, str) and single_id.isdigit():
            material_ids.append(int(single_id))

        multi_ids = payload.get("sales_material_ids")
        if isinstance(multi_ids, list):
            for item in multi_ids:
                if isinstance(item, int):
                    material_ids.append(item)
                elif isinstance(item, str) and item.isdigit():
                    material_ids.append(int(item))

        for material_id in material_ids:
            current = state.setdefault(
                material_id,
                {"count": 0, "last_sent_at": None, "message_ids": []},
            )
            current["count"] += 1
            current["last_sent_at"] = row.created_at.isoformat() if row.created_at else None
            current["message_ids"].append(row.id)

    return state


def build_sales_material_prompt_block(
    materials: Iterable[AgentSalesMaterial],
    sent_state: Dict[int, Dict[str, Any]],
) -> str:
    items = list(materials)
    if not items:
        return ""

    lines = [
        "--- SALES MATERIAL LIBRARY ---",
        "You may ask the system to send a sales material after your text reply when it clearly helps the customer.",
        "Rules:",
        "- Only send a material when it is directly relevant to the customer's current request.",
        "- Prefer materials not yet sent in this conversation.",
        "- Do not resend a previously sent material unless the customer clearly asks for it again.",
        "- Never mention internal IDs in your visible reply.",
        "- Link materials will be sent as a follow-up message containing the URL.",
        "Available materials:",
    ]
    for material in items:
        sent_info = sent_state.get(int(material.id or 0), {})
        sent_label = (
            f"yes ({sent_info.get('count', 0)}x, last at {sent_info.get('last_sent_at')})"
            if sent_info
            else "no"
        )
        kind = sales_material_kind_for_material(material)
        resolved_url = resolve_sales_material_public_url(material)
        lines.extend(
            [
                f"- Material ID {material.id}: {material.filename}",
                f"  Type: {kind} ({material.media_type})",
                f"  Description: {material.description or 'No description provided.'}",
                *( [f"  URL: {resolved_url}"] if resolved_url else [] ),
                f"  Already sent in this conversation: {sent_label}",
            ]
        )
    return "\n".join(lines)
