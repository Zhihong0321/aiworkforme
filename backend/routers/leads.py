from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from sqlmodel import SQLModel

from src.adapters.api.dependencies import AuthContext, require_tenant_access
from src.adapters.db.crm_models import Lead
from src.app.runtime.leads_service import delete_lead_and_children, get_tenant_lead_or_404, set_lead_mode_value
from src.infra.database import get_session

router = APIRouter(prefix="/api/v1/leads", tags=["Lead Management"])


class LeadModeRequest(SQLModel):
    mode: str


@router.get("/", response_model=list[Lead])
def list_leads(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    return session.exec(select(Lead).where(Lead.tenant_id == auth.tenant.id)).all()


@router.post("/", response_model=Lead)
def create_lead(
    lead: Lead,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    lead.tenant_id = auth.tenant.id
    # Workspace is now optional at write-time; runtime can resolve default lazily.
    lead.workspace_id = None
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead


@router.delete("/{lead_id}")
def delete_lead(
    lead_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    lead = get_tenant_lead_or_404(session, auth.tenant.id, lead_id)
    delete_lead_and_children(session, auth.tenant.id, lead)
    return {"status": "deleted", "lead_id": lead_id}


@router.post("/{lead_id}/mode", response_model=Lead)
def set_lead_mode(
    lead_id: int,
    payload: LeadModeRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    lead = get_tenant_lead_or_404(session, auth.tenant.id, lead_id)
    lead = set_lead_mode_value(lead, payload.mode)
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead
