"""
MODULE: Platform Settings Routes
PURPOSE: Boolean platform setting endpoints for admin configuration.
DOES: Read/write system settings with audit logging.
DOES NOT: Modify tenant/user records or provider routing.
INVARIANTS: Existing key names and endpoint contract remain stable.
SAFE CHANGE: Add new settings as separate endpoints for discoverability.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from src.adapters.api.dependencies import AuthContext, require_platform_admin
from src.adapters.db.audit_recorder import record_admin_audit
from src.adapters.db.system_settings import get_bool_system_setting
from src.adapters.db.tenant_models import SystemSetting
from src.infra.database import get_session

from .platform_schemas import BooleanSettingResponse, BooleanSettingUpdateRequest

router = APIRouter()


@router.get("/settings/record-context-prompt", response_model=BooleanSettingResponse)
def get_record_context_prompt_setting(
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    value = get_bool_system_setting(session, "record_context_prompt", default=False)
    return BooleanSettingResponse(key="record_context_prompt", value=value)


@router.put("/settings/record-context-prompt", response_model=BooleanSettingResponse)
def upsert_record_context_prompt_setting(
    payload: BooleanSettingUpdateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    setting = session.get(SystemSetting, "record_context_prompt")
    value_as_string = "true" if payload.value else "false"
    if not setting:
        setting = SystemSetting(key="record_context_prompt", value=value_as_string)
    else:
        setting.value = value_as_string

    session.add(setting)
    session.commit()

    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="platform_setting.update",
        target_type="system_setting",
        target_id="record_context_prompt",
        metadata={"value": payload.value},
    )
    return BooleanSettingResponse(key="record_context_prompt", value=payload.value)
