"""
MODULE: Schema Compatibility Checks
PURPOSE: Validate required DB columns for critical runtime paths.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Set

from sqlalchemy import text
from sqlalchemy.engine import Engine


REQUIRED_ET_MESSAGES_COLUMNS: List[str] = [
    "id",
    "tenant_id",
    "lead_id",
    "thread_id",
    "channel",
    "direction",
    "text_content",
    "media_url",
    "raw_payload",
    "delivery_status",
    "created_at",
    "updated_at",
    "llm_provider",
    "llm_model",
    "llm_prompt_tokens",
    "llm_completion_tokens",
    "llm_total_tokens",
    "llm_estimated_cost_usd",
]


def _get_table_columns(engine: Engine, table_name: str) -> Set[str]:
    dialect = engine.dialect.name
    with engine.connect() as conn:
        if dialect == "postgresql":
            rows = conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = :table_name
                    """
                ),
                {"table_name": table_name},
            ).fetchall()
            return {str(r[0]) for r in rows}

        if dialect == "sqlite":
            rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            return {str(r[1]) for r in rows}  # 2nd column is name

    return set()


def evaluate_message_schema_compat(engine: Engine) -> Dict[str, object]:
    existing = _get_table_columns(engine, "et_messages")
    missing = [c for c in REQUIRED_ET_MESSAGES_COLUMNS if c not in existing]
    return {
        "ok": len(missing) == 0,
        "table": "et_messages",
        "required_columns": REQUIRED_ET_MESSAGES_COLUMNS,
        "existing_columns": sorted(existing),
        "missing_columns": missing,
        "checked_at": datetime.utcnow().isoformat(),
        "dialect": engine.dialect.name,
    }
