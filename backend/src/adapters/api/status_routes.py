"""
MODULE: Status Routes
PURPOSE: Liveness/readiness and root status endpoints.
DOES: Provide API status without business side effects.
DOES NOT: Perform migrations or mutate domain/application state.
INVARIANTS: Endpoint paths and response shape remain backward-compatible.
SAFE CHANGE: Add new status checks behind existing response keys.
"""

from datetime import datetime
import importlib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlmodel import Session

router = APIRouter(tags=["Health Check"])


def _get_session():
    get_session = importlib.import_module("src.infra.database").get_session
    yield from get_session()


@router.get("/api/v1/", tags=["Status"])
def read_root() -> dict:
    return {"status": "Z.ai Backend API is running (Refactored)"}


@router.get("/api/v1/health")
def health_check() -> dict:
    return {"status": "ok", "service": "aiworkforme-backend", "version": "1.0.0-soc"}


@router.get("/api/v1/ready")
def readiness_check(db_session: Session = Depends(_get_session)) -> dict:
    try:
        engine = importlib.import_module("src.infra.database").engine
        startup_health = importlib.import_module("src.infra.lifecycle").STARTUP_HEALTH
        evaluate_message_schema_compat = importlib.import_module(
            "src.infra.schema_checks"
        ).evaluate_message_schema_compat
        db_session.execute(text("SELECT 1"))
        live_schema = evaluate_message_schema_compat(engine)
        startup_ready = bool(startup_health.get("ready"))
        schema_ready = bool(live_schema.get("ok"))
        if not startup_ready or not schema_ready:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "not_ready",
                    "reason": "schema_incompatible",
                    "startup_health": startup_health,
                    "live_schema": live_schema,
                },
            )
        return {
            "status": "ready",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "schema": {"ok": True},
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Database unreachable")
