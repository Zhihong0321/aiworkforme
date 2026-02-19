"""
MODULE: LLM Cost Estimator
PURPOSE: Estimate per-call USD cost from provider/model token usage.
"""
import os

DEFAULT_MODEL_RATES_PER_1M = {
    "uniapi": {
        "deepseek-v3.2": {"input": 0.236776, "output": 0.236776},
        "deepseek-v3.2-speciale": {"input": 0.240199, "output": 0.240199},
        "doubao-seed-1-6-251015": {"input": 0.890750, "output": 0.890750},
        "gemini-3-flash-preview": {"input": 0.891334, "output": 0.891334},
        "gpt-5-nano-2025-08-07": {"input": 0.339729, "output": 0.339729},
        "gpt-5.1-chat-latest": {"input": 6.698630, "output": 6.698630},
        "gpt-oss-120b": {"input": 0.133501, "output": 0.133501},
        "grok-4-1-fast": {"input": 0.180311, "output": 0.180311},
    }
}


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

    provider_rates = DEFAULT_MODEL_RATES_PER_1M.get((provider or "").strip().lower(), {})
    model_rates = provider_rates.get((model or "").strip(), {})
    default_rate = model_rates.get(side.lower())
    if default_rate is not None:
        try:
            return float(default_rate)
        except (TypeError, ValueError):
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
