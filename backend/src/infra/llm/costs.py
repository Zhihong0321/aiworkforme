"""
MODULE: LLM Cost Estimator
PURPOSE: Estimate per-call USD cost from provider/model token usage.
"""
import os


def _env_key(provider: str, model: str, side: str) -> str:
    provider_key = "".join(ch if ch.isalnum() else "_" for ch in (provider or "")).upper()
    model_key = "".join(ch if ch.isalnum() else "_" for ch in (model or "")).upper()
    side_key = side.upper()
    return f"LLM_COST_{provider_key}_{model_key}_{side_key}_PER_1M"


def _provider_env_key(provider: str, side: str) -> str:
    provider_key = "".join(ch if ch.isalnum() else "_" for ch in (provider or "")).upper()
    side_key = side.upper()
    return f"LLM_COST_{provider_key}_{side_key}_PER_1M"


def _read_rate(provider: str, model: str, side: str) -> float:
    specific = os.getenv(_env_key(provider, model, side))
    if specific is not None:
        try:
            return float(specific)
        except ValueError:
            return 0.0

    generic = os.getenv(_provider_env_key(provider, side))
    if generic is not None:
        try:
            return float(generic)
        except ValueError:
            return 0.0
    return 0.0


def estimate_llm_cost_usd(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    input_rate_per_1m = _read_rate(provider, model, "input")
    output_rate_per_1m = _read_rate(provider, model, "output")
    cost = (max(prompt_tokens, 0) / 1_000_000.0) * input_rate_per_1m
    cost += (max(completion_tokens, 0) / 1_000_000.0) * output_rate_per_1m
    return round(cost, 6)
