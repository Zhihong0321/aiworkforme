from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Dict
from pydantic import BaseModel

from database import get_session
from models import SystemSetting
from dependencies import get_zai_client
from zai_client import ZaiClient

router = APIRouter(prefix="/api/v1/settings", tags=["System Settings"])

class APIKeyRequest(BaseModel):
    api_key: str

@router.get("/zai-key")
def get_zai_key(session: Session = Depends(get_session)):
    setting = session.get(SystemSetting, "zai_api_key")
    if setting and setting.value:
        # Return masked key
        masked = f"{setting.value[:4]}...{setting.value[-4:]}"
        return {"status": "set", "masked_key": masked}
    return {"status": "not_set", "masked_key": None}

@router.post("/zai-key")
def update_zai_key(
    request: APIKeyRequest, 
    session: Session = Depends(get_session),
    zai_client: ZaiClient = Depends(get_zai_client)
):
    setting = session.get(SystemSetting, "zai_api_key")
    if not setting:
        setting = SystemSetting(key="zai_api_key", value=request.api_key)
        session.add(setting)
    else:
        setting.value = request.api_key
        session.add(setting)
    
    session.commit()
    
    # Update live client
    zai_client.update_api_key(request.api_key)
    
    return {"status": "updated"}
