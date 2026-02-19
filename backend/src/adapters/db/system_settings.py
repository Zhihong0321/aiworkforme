"""
MODULE: System Settings Utilities
PURPOSE: Typed helpers for reading string-backed system settings.
"""
from typing import Optional

from sqlmodel import Session

from src.adapters.db.tenant_models import SystemSetting


def parse_bool_setting(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def get_bool_system_setting(session: Session, key: str, default: bool = False) -> bool:
    setting = session.get(SystemSetting, key)
    if not setting:
        return default
    return parse_bool_setting(setting.value, default=default)
