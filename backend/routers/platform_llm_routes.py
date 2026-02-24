"""
MODULE: Platform LLM And API Key Routes
PURPOSE: Provider key management and LLM routing/config/benchmark endpoints.
DOES: Read/write system settings and trigger router refresh operations.
DOES NOT: Manage tenants/users or export audit data.
INVARIANTS: Existing provider names and endpoint payloads remain compatible.
SAFE CHANGE: Introduce providers through shared validation helpers.
"""

import json
import time
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from src.adapters.api.dependencies import (
    AuthContext,
    get_zai_client,
    refresh_llm_router_config,
    refresh_llm_task_model_config,
    refresh_provider_keys_from_db,
    require_platform_admin,
)
from src.adapters.db.audit_recorder import record_admin_audit
from src.adapters.db.tenant_models import SystemSetting
from src.adapters.zai.client import ZaiClient
from src.infra.database import get_session
from src.infra.llm.schemas import LLMTask

from .platform_key_validation import (
    mask_secret,
    provider_meta,
    validate_uniapi_key,
    validate_zai_key,
)
from .platform_schemas import (
    ApiKeyRequest,
    ApiKeyStatus,
    ApiKeyValidateRequest,
    ApiKeyValidationResponse,
    BenchmarkModelSummary,
    BenchmarkRunItem,
    LLMRoutingUpdateRequest,
    LLMTaskModelConfigUpdateRequest,
    ModelBenchmarkRequest,
    ModelBenchmarkResponse,
    PROVIDER_SETTINGS,
)

router = APIRouter()


@router.get("/api-keys", response_model=List[ApiKeyStatus])
def list_api_keys(
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    results: List[ApiKeyStatus] = []
    for provider, (setting_key, head, tail) in PROVIDER_SETTINGS.items():
        setting = session.get(SystemSetting, setting_key)
        if setting and setting.value:
            results.append(
                ApiKeyStatus(
                    provider=provider,
                    status="set",
                    masked_key=mask_secret(setting.value, head, tail),
                )
            )
        else:
            results.append(ApiKeyStatus(provider=provider, status="not_set", masked_key=None))
    return results


@router.post("/api-keys/{provider}", response_model=ApiKeyStatus)
def upsert_api_key(
    provider: str,
    payload: ApiKeyRequest,
    session: Session = Depends(get_session),
    zai_client: ZaiClient = Depends(get_zai_client),
    context: AuthContext = Depends(require_platform_admin),
):
    setting_key, head, tail = provider_meta(provider)
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="api_key is required")

    setting = session.get(SystemSetting, setting_key)
    action = "api_key.create"
    if not setting:
        setting = SystemSetting(key=setting_key, value=api_key)
        session.add(setting)
    else:
        setting.value = api_key
        session.add(setting)
        action = "api_key.rotate"
    session.commit()

    if setting_key == "zai_api_key":
        zai_client.update_api_key(api_key)

    refresh_provider_keys_from_db(session)

    masked = mask_secret(api_key, head, tail)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action=action,
        target_type="system_setting",
        target_id=setting_key,
        metadata={"provider": provider.lower(), "masked": masked},
    )
    return ApiKeyStatus(provider=provider.lower(), status="set", masked_key=masked)


@router.delete("/api-keys/{provider}", response_model=ApiKeyStatus)
def revoke_api_key(
    provider: str,
    session: Session = Depends(get_session),
    zai_client: ZaiClient = Depends(get_zai_client),
    context: AuthContext = Depends(require_platform_admin),
):
    setting_key, _head, _tail = provider_meta(provider)
    setting = session.get(SystemSetting, setting_key)
    if setting:
        session.delete(setting)
        session.commit()

    if setting_key == "zai_api_key":
        zai_client.update_api_key("")

    refresh_provider_keys_from_db(session)

    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="api_key.revoke",
        target_type="system_setting",
        target_id=setting_key,
        metadata={"provider": provider.lower()},
    )
    return ApiKeyStatus(provider=provider.lower(), status="not_set", masked_key=None)


@router.post("/api-keys/{provider}/validate", response_model=ApiKeyValidationResponse)
def validate_api_key(
    provider: str,
    payload: ApiKeyValidateRequest,
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    setting_key, _head, _tail = provider_meta(provider)
    input_key = (payload.api_key or "").strip()
    if input_key:
        api_key = input_key
    else:
        setting = session.get(SystemSetting, setting_key)
        api_key = (setting.value if setting and setting.value else "").strip()

    checked_at = datetime.utcnow()
    if not api_key:
        return ApiKeyValidationResponse(
            provider=provider.lower(),
            status="not_set",
            detail="No key to validate. Enter one or save it first.",
            checked_at=checked_at,
        )

    normalized = provider.strip().lower()
    if normalized == "zai":
        is_valid, detail = validate_zai_key(api_key)
    elif normalized == "uniapi":
        is_valid, detail = validate_uniapi_key(api_key)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported provider")

    return ApiKeyValidationResponse(
        provider=normalized,
        status="valid" if is_valid else "invalid",
        detail=detail,
        checked_at=checked_at,
    )


@router.get("/llm/routing")
def get_llm_routing(
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    from src.adapters.api.dependencies import llm_router

    defaults = {
        t.value: llm_router.routing_config.get(t, llm_router.default_provider)
        for t in LLMTask
    }
    setting = session.get(SystemSetting, "llm_routing_config")
    if setting and setting.value:
        stored = json.loads(setting.value)
        if isinstance(stored, dict):
            valid_tasks = {t.value for t in LLMTask}
            defaults.update(
                {
                    k: str(v).strip()
                    for k, v in stored.items()
                    if k in valid_tasks and isinstance(v, str) and str(v).strip()
                }
            )
    return defaults


@router.get("/llm/task-models")
def get_llm_task_models(
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    defaults = {t.value: None for t in LLMTask}
    setting = session.get(SystemSetting, "llm_task_model_config")
    if setting and setting.value:
        stored = json.loads(setting.value)
        if isinstance(stored, dict):
            defaults.update(stored)
        return defaults

    from src.adapters.api.dependencies import llm_router

    current = {k.value: v for k, v in llm_router.task_model_config.items() if v}
    if current:
        defaults.update(current)
    return defaults


@router.post("/llm/routing")
def update_llm_routing(
    payload: LLMRoutingUpdateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    valid_tasks = {t.value for t in LLMTask}
    for task in payload.config.keys():
        if task not in valid_tasks:
            raise HTTPException(status_code=400, detail=f"Invalid LLM task: {task}")

    setting = session.get(SystemSetting, "llm_routing_config")
    if not setting:
        setting = SystemSetting(key="llm_routing_config", value=json.dumps(payload.config))
    else:
        setting.value = json.dumps(payload.config)

    session.add(setting)
    session.commit()

    refresh_llm_router_config(session)

    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="llm_routing.update",
        target_type="system_setting",
        target_id="llm_routing_config",
        metadata={"config": payload.config},
    )

    return {"status": "updated", "config": payload.config}


@router.post("/llm/task-models")
def update_llm_task_models(
    payload: LLMTaskModelConfigUpdateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    valid_tasks = {t.value for t in LLMTask}
    normalized: dict = {}
    for task, model in payload.config.items():
        if task not in valid_tasks:
            raise HTTPException(status_code=400, detail=f"Invalid LLM task: {task}")
        normalized[task] = (str(model).strip() if model is not None else None)

    setting = session.get(SystemSetting, "llm_task_model_config")
    if not setting:
        setting = SystemSetting(key="llm_task_model_config", value=json.dumps(normalized))
    else:
        setting.value = json.dumps(normalized)

    session.add(setting)
    session.commit()
    refresh_llm_task_model_config(session)

    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="llm_task_model_config.update",
        target_type="system_setting",
        target_id="llm_task_model_config",
        metadata={"config": normalized},
    )

    return {"status": "updated", "config": normalized}


@router.get("/llm/providers")
def list_llm_providers(
    _context: AuthContext = Depends(require_platform_admin),
):
    from src.adapters.api.dependencies import llm_router

    return list(llm_router.providers.keys())


@router.get("/llm/tasks")
def list_llm_tasks(
    _context: AuthContext = Depends(require_platform_admin),
):
    return [t.value for t in LLMTask]


@router.get("/llm/models")
def list_llm_models(
    _context: AuthContext = Depends(require_platform_admin),
):
    from src.adapters.api.dependencies import llm_router

    results: List[dict] = []
    for provider_name, provider in llm_router.providers.items():
        if hasattr(provider, "list_supported_models"):
            try:
                items = provider.list_supported_models()
                if isinstance(items, list):
                    results.extend(items)
            except Exception:
                continue
        else:
            results.append({"provider": provider_name, "model": "dynamic", "schema": "runtime"})
    return results


@router.post("/llm/benchmark", response_model=ModelBenchmarkResponse)
async def benchmark_llm_models(
    payload: ModelBenchmarkRequest,
    _context: AuthContext = Depends(require_platform_admin),
):
    from src.adapters.api.dependencies import llm_router

    provider_name = (payload.provider or "").strip().lower() or "uniapi"
    if provider_name not in llm_router.providers:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_name}")

    provider = llm_router.providers.get(provider_name)
    if not provider or not provider.is_healthy():
        raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' is not configured")

    models = [m.strip() for m in (payload.models or []) if isinstance(m, str) and m.strip()]
    if not models:
        raise HTTPException(status_code=400, detail="At least one model is required")

    runs_per_model = min(max(int(payload.runs_per_model or 1), 1), 20)
    prompt = (payload.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    max_tokens = min(max(int(payload.max_tokens or 64), 1), 4096)
    temperature = float(payload.temperature if payload.temperature is not None else 0.2)
    if temperature < 0:
        temperature = 0
    if temperature > 2:
        temperature = 2

    run_results: List[BenchmarkRunItem] = []
    summary_map: dict[str, dict] = {}

    for model in models:
        for run_index in range(1, runs_per_model + 1):
            t0 = time.perf_counter()
            try:
                response = await llm_router.execute(
                    task=LLMTask.CONVERSATION,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=model,
                    provider=provider_name,
                    disable_fallback=True,
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                usage = response.usage or {}
                prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
                completion_tokens = int(usage.get("completion_tokens", 0) or 0)
                total_tokens = int(usage.get("total_tokens", 0) or (prompt_tokens + completion_tokens))
                provider_info = response.provider_info or {}
                schema = provider_info.get("schema")

                row = BenchmarkRunItem(
                    model=model,
                    provider=provider_info.get("provider") or provider_name,
                    schema=schema,
                    run_index=run_index,
                    ok=True,
                    latency_ms=latency_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
            except Exception as exc:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                row = BenchmarkRunItem(
                    model=model,
                    provider=provider_name,
                    schema=None,
                    run_index=run_index,
                    ok=False,
                    latency_ms=latency_ms,
                    error=str(exc),
                )
            run_results.append(row)

            key = f"{row.provider}|{row.model}|{row.schema or ''}"
            bucket = summary_map.setdefault(
                key,
                {
                    "model": row.model,
                    "provider": row.provider,
                    "schema": row.schema,
                    "runs": 0,
                    "success_runs": 0,
                    "failed_runs": 0,
                    "latencies": [],
                    "prompt_tokens": [],
                    "completion_tokens": [],
                    "total_tokens": [],
                },
            )
            bucket["runs"] += 1
            if row.ok:
                bucket["success_runs"] += 1
                if row.latency_ms is not None:
                    bucket["latencies"].append(row.latency_ms)
                bucket["prompt_tokens"].append(row.prompt_tokens)
                bucket["completion_tokens"].append(row.completion_tokens)
                bucket["total_tokens"].append(row.total_tokens)
            else:
                bucket["failed_runs"] += 1

    summaries: List[BenchmarkModelSummary] = []
    for item in summary_map.values():
        latencies = item["latencies"]
        prompt_tokens = item["prompt_tokens"]
        completion_tokens = item["completion_tokens"]
        total_tokens = item["total_tokens"]
        summaries.append(
            BenchmarkModelSummary(
                model=item["model"],
                provider=item["provider"],
                schema=item["schema"],
                runs=item["runs"],
                success_runs=item["success_runs"],
                failed_runs=item["failed_runs"],
                avg_latency_ms=(sum(latencies) / len(latencies)) if latencies else None,
                min_latency_ms=min(latencies) if latencies else None,
                max_latency_ms=max(latencies) if latencies else None,
                avg_total_tokens=(sum(total_tokens) / len(total_tokens)) if total_tokens else None,
                avg_prompt_tokens=(sum(prompt_tokens) / len(prompt_tokens)) if prompt_tokens else None,
                avg_completion_tokens=(sum(completion_tokens) / len(completion_tokens))
                if completion_tokens
                else None,
            )
        )

    summaries.sort(
        key=lambda x: (
            x.avg_latency_ms if x.avg_latency_ms is not None else float("inf"),
            -(x.success_runs or 0),
        )
    )

    return ModelBenchmarkResponse(
        provider=provider_name,
        generated_at=datetime.utcnow(),
        prompt=prompt,
        runs_per_model=runs_per_model,
        results=run_results,
        summary=summaries,
    )
