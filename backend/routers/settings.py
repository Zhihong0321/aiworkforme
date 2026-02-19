from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Dict
from pydantic import BaseModel

from src.infra.database import get_session
from src.adapters.db.tenant_models import SystemSetting
from src.adapters.api.dependencies import get_zai_client, refresh_provider_keys_from_db
from src.adapters.zai.client import ZaiClient

router = APIRouter(prefix="/api/v1/settings", tags=["System Settings"])

class APIKeyRequest(BaseModel):
    api_key: str

@router.get("/zai-key")
def get_zai_key(session: Session = Depends(get_session)):
    setting = session.get(SystemSetting, "zai_api_key")
    if setting and setting.value:
        masked = f"{setting.value[:4]}...{setting.value[-4:]}"
        return {"status": "set", "masked_key": masked}
    return {"status": "not_set", "masked_key": None}

@router.get("/uniapi-key")
def get_uniapi_key(session: Session = Depends(get_session)):
    setting = session.get(SystemSetting, "uniapi_key")
    if setting and setting.value:
        masked = f"{setting.value[:2]}...{setting.value[-2:]}"
        return {"status": "set", "masked_key": masked}
    return {"status": "not_set", "masked_key": None}

@router.post("/zai-key")
def update_zai_key(
    request: APIKeyRequest, 
    session: Session = Depends(get_session),
    zai_client: ZaiClient = Depends(get_zai_client)
):
    _save_setting(session, "zai_api_key", request.api_key)
    zai_client.update_api_key(request.api_key)
    refresh_provider_keys_from_db(session)
    return {"status": "updated"}

@router.post("/uniapi-key")
def update_uniapi_key(
    request: APIKeyRequest, 
    session: Session = Depends(get_session)
):
    _save_setting(session, "uniapi_key", request.api_key)
    refresh_provider_keys_from_db(session)
    return {"status": "updated"}

def _save_setting(session: Session, key: str, value: str):
    setting = session.get(SystemSetting, key)
    if not setting:
        setting = SystemSetting(key=key, value=value)
        session.add(setting)
    else:
        setting.value = value
        session.add(setting)
    session.commit()
