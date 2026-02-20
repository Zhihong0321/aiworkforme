"""
MODULE: Platform Router Schemas
PURPOSE: Request/response DTOs used by platform admin endpoints.
DOES: Define schema models and constants shared across route modules.
DOES NOT: Perform IO, validation side effects, or route registration.
INVARIANTS: Field names/types must remain API-compatible.
SAFE CHANGE: Add fields in backward-compatible way only.
"""

from datetime import datetime
from typing import List, Optional

from sqlmodel import SQLModel

from src.domain.entities.enums import Role, TenantStatus


class TenantCreateRequest(SQLModel):
    name: str


class TenantResponse(SQLModel):
    id: int
    name: str
    status: TenantStatus
    created_at: datetime


class UserCreateRequest(SQLModel):
    email: str
    password: str
    is_platform_admin: bool = False


class UserResponse(SQLModel):
    id: int
    email: str
    is_active: bool
    is_platform_admin: bool
    created_at: datetime


class MembershipCreateRequest(SQLModel):
    user_id: int
    role: Role


class MembershipResponse(SQLModel):
    id: int
    user_id: int
    tenant_id: int
    role: Role
    is_active: bool


class TenantStatusUpdateRequest(SQLModel):
    status: TenantStatus


class UserStatusUpdateRequest(SQLModel):
    is_active: bool


class MembershipStatusUpdateRequest(SQLModel):
    is_active: bool


class AdminAuditLogResponse(SQLModel):
    id: int
    actor_user_id: int
    tenant_id: int | None
    action: str
    target_type: str
    target_id: str | None
    details: dict
    created_at: datetime


class SecurityEventLogResponse(SQLModel):
    id: int
    actor_user_id: int | None
    tenant_id: int | None
    event_type: str
    endpoint: str
    method: str
    status_code: int
    reason: str
    details: dict
    created_at: datetime


class PlatformMessageHistoryItem(SQLModel):
    message_id: int
    tenant_id: int
    tenant_name: str | None = None
    lead_id: int
    lead_external_id: str | None = None
    thread_id: int | None = None
    channel: str
    direction: str
    text_content: str | None = None
    delivery_status: str
    ai_generated: bool
    ai_trace: dict
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_prompt_tokens: int | None = None
    llm_completion_tokens: int | None = None
    llm_total_tokens: int | None = None
    llm_estimated_cost_usd: float | None = None
    created_at: datetime


class PlatformSystemHealthResponse(SQLModel):
    ready: bool
    checks: dict
    blockers: List[str]
    checked_at: datetime


class ApiKeyRequest(SQLModel):
    api_key: str


class ApiKeyStatus(SQLModel):
    provider: str
    status: str
    masked_key: str | None = None


class ApiKeyValidateRequest(SQLModel):
    api_key: Optional[str] = None


class ApiKeyValidationResponse(SQLModel):
    provider: str
    status: str
    detail: str
    checked_at: datetime


class LLMRoutingUpdateRequest(SQLModel):
    config: dict


class LLMTaskModelConfigUpdateRequest(SQLModel):
    config: dict


class BooleanSettingResponse(SQLModel):
    key: str
    value: bool


class BooleanSettingUpdateRequest(SQLModel):
    value: bool


class BenchmarkRunItem(SQLModel):
    model: str
    provider: str
    schema: str | None = None
    run_index: int
    ok: bool
    latency_ms: int | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    error: str | None = None


class BenchmarkModelSummary(SQLModel):
    model: str
    provider: str
    schema: str | None = None
    runs: int
    success_runs: int
    failed_runs: int
    avg_latency_ms: float | None = None
    min_latency_ms: int | None = None
    max_latency_ms: int | None = None
    avg_total_tokens: float | None = None
    avg_prompt_tokens: float | None = None
    avg_completion_tokens: float | None = None


class ModelBenchmarkRequest(SQLModel):
    models: List[str]
    prompt: str = "Summarize solar lead qualification in one sentence."
    runs_per_model: int = 2
    max_tokens: int = 256
    temperature: float = 0.2
    provider: str = "uniapi"


class ModelBenchmarkResponse(SQLModel):
    provider: str
    generated_at: datetime
    prompt: str
    runs_per_model: int
    results: List[BenchmarkRunItem]
    summary: List[BenchmarkModelSummary]


PROVIDER_SETTINGS = {
    "zai": ("zai_api_key", 4, 4),
    "uniapi": ("uniapi_key", 2, 2),
}
