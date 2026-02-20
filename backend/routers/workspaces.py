import csv
import io
import re
from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from sqlmodel import SQLModel
from src.infra.database import get_session
from src.adapters.db.crm_models import Workspace, Lead, StrategyVersion, StrategyStatus
from src.adapters.db.agent_models import Agent
from src.adapters.api.dependencies import require_tenant_access, AuthContext
from src.app.runtime.leads_service import delete_lead_and_children, set_lead_mode_value

router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspace Management"])


class LeadModeRequest(SQLModel):
    mode: str  # on_hold | working


class LeadCsvImportResponse(SQLModel):
    workspace_id: int
    rows_received: int
    leads_created: int
    skipped_duplicates: int
    skipped_invalid: int
    errors: List[str] = []


def _canonical_lead_key(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    digits = re.sub(r"\D+", "", raw)
    if len(digits) >= 8:
        # Keep local/international variants aligned to one key.
        if digits.startswith("0") and len(digits) >= 9:
            return f"phone:6{digits}"
        if digits.startswith("60") and len(digits) >= 10:
            return f"phone:{digits}"
        return f"phone:{digits}"
    return f"raw:{raw.lower()}"


def _extract_row_fields(row: dict) -> tuple[Optional[str], Optional[str]]:
    external_candidates = [
        "external_id", "phone", "phone_number", "mobile", "whatsapp", "contact", "number"
    ]
    name_candidates = ["name", "full_name", "contact_name"]

    external_id = None
    name = None
    for key in external_candidates:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            external_id = value.strip()
            break
    for key in name_candidates:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            name = value.strip()
            break
    return external_id, name

@router.get("/", response_model=List[Workspace])
def list_workspaces(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    return session.exec(select(Workspace).where(Workspace.tenant_id == auth.tenant.id)).all()

@router.post("/", response_model=Workspace)
def create_workspace(
    workspace: Workspace, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    workspace.tenant_id = auth.tenant.id
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace

@router.put("/{workspace_id}", response_model=Workspace)
def update_workspace(
    workspace_id: int, 
    agent_id: Optional[int] = None, 
    name: Optional[str] = None, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if agent_id is not None:
        # Verify agent exists
        agent = session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        ws.agent_id = agent_id
    
    if name:
        ws.name = name
    
    session.add(ws)
    session.commit()
    session.refresh(ws)
    return ws

@router.get("/{workspace_id}/leads", response_model=List[Lead])
def get_workspace_leads(
    workspace_id: int, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return session.exec(select(Lead).where(Lead.workspace_id == workspace_id)).all()

@router.get("/{workspace_id}/strategy", response_model=Optional[StrategyVersion])
def get_workspace_strategy(
    workspace_id: int, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return session.exec(
        select(StrategyVersion)
        .where(StrategyVersion.workspace_id == workspace_id)
        .where(StrategyVersion.status == StrategyStatus.ACTIVE)
    ).first()

@router.post("/{workspace_id}/strategy", response_model=StrategyVersion)
def update_workspace_strategy(
    workspace_id: int, 
    payload: StrategyVersion, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    # Deactivate old ones
    old_strategies = session.exec(
        select(StrategyVersion)
        .where(StrategyVersion.workspace_id == workspace_id)
    ).all()
    for old in old_strategies:
        old.status = StrategyStatus.ROLLED_BACK
        session.add(old)
    
    # Create new active one
    payload.workspace_id = workspace_id
    payload.status = StrategyStatus.ACTIVE
    payload.version_number = len(old_strategies) + 1
    session.add(payload)
    session.commit()
    session.refresh(payload)
    return payload
@router.post("/{workspace_id}/leads", response_model=Lead)
def create_lead(
    workspace_id: int, 
    lead: Lead, 
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    lead.workspace_id = workspace_id
    lead.tenant_id = auth.tenant.id
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead


@router.post("/{workspace_id}/leads/import-csv", response_model=LeadCsvImportResponse)
async def import_workspace_leads_csv(
    workspace_id: int,
    file: UploadFile = File(...),
    has_header: bool = Form(True),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="CSV file is required")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc

    existing = session.exec(
        select(Lead).where(
            Lead.tenant_id == auth.tenant.id,
            Lead.workspace_id == workspace_id,
        )
    ).all()
    existing_keys: set[str] = set()
    for lead in existing:
        key = _canonical_lead_key(lead.external_id)
        if key:
            existing_keys.add(key)

    rows_received = 0
    leads_created = 0
    skipped_duplicates = 0
    skipped_invalid = 0
    errors: List[str] = []

    reader_stream = io.StringIO(text)
    rows: List[dict] = []
    if has_header:
        reader = csv.DictReader(reader_stream)
        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV header is missing")
        rows = [dict(row or {}) for row in reader]
    else:
        reader = csv.reader(reader_stream)
        for cells in reader:
            value = (cells[0] if len(cells) > 0 else "").strip()
            name = (cells[1] if len(cells) > 1 else "").strip()
            rows.append({"external_id": value, "name": name})

    for idx, row in enumerate(rows, start=1):
        rows_received += 1
        external_id, name = _extract_row_fields(row)
        if not external_id:
            skipped_invalid += 1
            if len(errors) < 20:
                errors.append(f"Row {idx}: missing contact number/external_id.")
            continue

        canonical_key = _canonical_lead_key(external_id)
        if not canonical_key:
            skipped_invalid += 1
            if len(errors) < 20:
                errors.append(f"Row {idx}: invalid contact value '{external_id}'.")
            continue

        if canonical_key in existing_keys:
            skipped_duplicates += 1
            continue

        lead = Lead(
            tenant_id=auth.tenant.id,
            workspace_id=workspace_id,
            external_id=external_id.strip(),
            name=name or None,
            stage="NEW",
            tags=[],
            created_at=datetime.utcnow(),
        )
        session.add(lead)
        existing_keys.add(canonical_key)
        leads_created += 1

    session.commit()
    return LeadCsvImportResponse(
        workspace_id=workspace_id,
        rows_received=rows_received,
        leads_created=leads_created,
        skipped_duplicates=skipped_duplicates,
        skipped_invalid=skipped_invalid,
        errors=errors,
    )


@router.delete("/{workspace_id}/leads/{lead_id}")
def delete_lead(
    workspace_id: int,
    lead_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")

    lead = session.get(Lead, lead_id)
    if not lead or lead.tenant_id != auth.tenant.id or lead.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    delete_lead_and_children(session, auth.tenant.id, lead)
    return {"status": "deleted", "lead_id": lead_id}


@router.post("/{workspace_id}/leads/{lead_id}/mode", response_model=Lead)
def set_lead_mode(
    workspace_id: int,
    lead_id: int,
    payload: LeadModeRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access),
):
    ws = session.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Workspace not found")

    lead = session.get(Lead, lead_id)
    if not lead or lead.tenant_id != auth.tenant.id or lead.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead = set_lead_mode_value(lead, payload.mode)
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead
