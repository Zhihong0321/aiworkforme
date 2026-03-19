#!/usr/bin/env python3
"""Run a simple customer-vs-agent self-play loop to compare conversation skill impact.

This script runs two simulations against the same customer preset:
1. Baseline agent prompt
2. Baseline agent prompt + human conversation skill

Both sides use UniAPI Gemini through the existing backend provider adapter.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from src.app.conversation_skills import (  # noqa: E402
    ConversationSkillContext,
    ConversationTaskKind,
    get_default_conversation_skill_registry,
)
from src.infra.llm.providers.uniapi import UniAPIProvider  # noqa: E402
from src.infra.llm.schemas import LLMMessage, LLMRequest, LLMResponse, LLMTask  # noqa: E402


DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"

BASE_AGENT_PROMPT = """You are Xiao Hao, a solar consultant for Eternalgy in Malaysia.
You are chatting with a lead on WhatsApp.

Goals:
- answer the lead clearly
- be concise and natural
- move the conversation forward when appropriate

Style:
- reply in simple conversational Chinese unless the user clearly switches language
- keep replies short
- sound like one real person, not a brochure
"""

def _load_human_base_skill() -> str:
    registry = get_default_conversation_skill_registry()
    ctx = ConversationSkillContext(
        task_kind=ConversationTaskKind.CONVERSATION,
        channel="whatsapp",
        agent_id=None,
        tenant_id=None,
    )
    for skill in registry.resolve(ctx):
        if skill.meta.skill_id == "human-base":
            return skill.body
    raise RuntimeError("human-base skill not found")


HUMAN_BASE_SKILL = _load_human_base_skill()


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    description: str
    opener: str
    customer_prompt: str


SCENARIOS: Dict[str, Scenario] = {
    "busy-deflector": Scenario(
        scenario_id="busy-deflector",
        description="Asks price, wants brochure first, avoids address and meeting details.",
        opener="hi",
        customer_prompt="""You are simulating a real WhatsApp lead for home solar.

Personality:
- cautious
- brief
- slightly skeptical
- dislikes repeated follow-up questions

Behavior:
- start by asking price
- if pushed too quickly for address, meeting time, or home visit, avoid answering directly
- ask for brochure or company name before trusting them
- if the other side feels pushy, become colder and shorter
- if the other side feels natural and respectful, become a bit warmer

Output rules:
- reply like a real human lead
- use short Chinese messages, with occasional simple English if natural
- you are the customer, never the salesperson
- never say you are roleplaying or simulating
- never explain your hidden rules
- if you would stop replying in real life, reply exactly [END]
""",
    ),
    "skeptical-homeowner": Scenario(
        scenario_id="skeptical-homeowner",
        description="Has never heard of the company and needs trust before giving details.",
        opener="你们做什么的？",
        customer_prompt="""You are simulating a real homeowner lead on WhatsApp.

Personality:
- skeptical
- practical
- not rude, but guarded

Behavior:
- ask what the company does
- ask the company name if the answer feels vague
- do not share address or appointment time unless trust is earned
- if the salesperson repeats the same ask, feel annoyed
- if they answer clearly and calmly, become more open

Output rules:
- reply in short natural Chinese
- you are the customer, never the salesperson
- never mention roleplay or hidden instructions
- if you would stop replying in real life, reply exactly [END]
""",
    ),
    "warm-but-busy": Scenario(
        scenario_id="warm-but-busy",
        description="Some interest, but low patience for friction or scheduling pressure.",
        opener="可以先简单介绍一下吗",
        customer_prompt="""You are simulating a real lead on WhatsApp.

Personality:
- polite
- mildly interested
- busy

Behavior:
- willing to hear a short explanation
- prefers WhatsApp over calls or visits at first
- if the salesperson is too aggressive, pull back
- if the salesperson is respectful, ask one or two more questions

Output rules:
- reply in short natural Chinese
- you are the customer, never the salesperson
- never mention roleplay or hidden instructions
- if you would stop replying in real life, reply exactly [END]
""",
    ),
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key", default="", help="UniAPI API key. Falls back to UNIAPI_API_KEY env var.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model name to use.")
    parser.add_argument("--scenario", default="busy-deflector", choices=sorted(SCENARIOS.keys()))
    parser.add_argument("--turns", type=int, default=4, help="Max agent turns per run.")
    parser.add_argument("--output", default="", help="Optional JSON output path.")
    parser.add_argument("--no-judge", action="store_true", help="Skip the transcript comparison judge step.")
    return parser.parse_args()


def _resolve_api_key(args: argparse.Namespace) -> str:
    api_key = str(args.api_key or "").strip()
    if api_key:
        return api_key
    api_key = str(__import__("os").environ.get("UNIAPI_API_KEY", "")).strip()
    if api_key:
        return api_key
    raise SystemExit("UNIAPI_API_KEY not provided. Pass --api-key or set UNIAPI_API_KEY.")


def _normalize_model_name(model: str) -> str:
    raw = str(model or "").strip()
    return raw or DEFAULT_MODEL


def _build_agent_prompt(use_skill: bool) -> str:
    return BASE_AGENT_PROMPT if not use_skill else f"{BASE_AGENT_PROMPT}\n\n{HUMAN_BASE_SKILL}"


def _to_llm_messages(system_prompt: str, transcript: List[Dict[str, str]]) -> List[LLMMessage]:
    messages = [LLMMessage(role="system", content=system_prompt)]
    for item in transcript:
        messages.append(LLMMessage(role=item["role"], content=item["content"]))
    return messages


def _curl_generate_text(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    transcript: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + list(transcript),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    command = [
        "curl.exe",
        "-4",
        "--http1.1",
        "--silent",
        "--show-error",
        "--request",
        "POST",
        "https://api.uniapi.io/v1/chat/completions",
        "--header",
        f"Authorization: Bearer {api_key}",
        "--header",
        "Content-Type: application/json",
        "--data",
        json.dumps(payload, ensure_ascii=False),
    ]
    proc = subprocess.run(
        command,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"curl UniAPI call failed: {stderr or 'unknown error'}")

    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    try:
        data = json.loads(stdout)
    except Exception as exc:
        raise RuntimeError(f"curl UniAPI response was not valid JSON: {stdout[:300]}") from exc

    choices = data.get("choices") or []
    text = str((((choices[0] or {}).get("message") or {}).get("content")) or "").strip() if choices else ""
    if text:
        return text

    if data.get("error"):
        raise RuntimeError(f"UniAPI error payload: {json.dumps(data['error'], ensure_ascii=False)}")
    raise RuntimeError("UniAPI returned no text candidates")


async def _generate_text(
    provider: UniAPIProvider,
    *,
    api_key: str,
    system_prompt: str,
    transcript: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    request = LLMRequest(
        task=LLMTask.CONVERSATION,
        messages=_to_llm_messages(system_prompt, transcript),
        temperature=temperature,
        max_tokens=max_tokens,
        extra_params={"model": model},
    )
    try:
        return _curl_generate_text(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            transcript=transcript,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception:
        response: LLMResponse = await provider.generate(request)
        text = str(response.content or "").strip()
        if text:
            return text
    raise RuntimeError("Model returned empty content")


async def _run_single_simulation(
    provider: UniAPIProvider,
    *,
    api_key: str,
    scenario: Scenario,
    model: str,
    turns: int,
    use_skill: bool,
) -> List[Dict[str, str]]:
    transcript: List[Dict[str, str]] = [{"role": "user", "content": scenario.opener}]
    agent_prompt = _build_agent_prompt(use_skill)

    for _ in range(max(1, turns)):
        agent_reply = await _generate_next_turn(
            provider,
            api_key=api_key,
            system_prompt=agent_prompt,
            transcript=transcript,
            speaker="AGENT",
            model=model,
            temperature=0.35,
            max_tokens=260,
        )
        transcript.append({"role": "assistant", "content": agent_reply})

        customer_reply = await _generate_next_turn(
            provider,
            api_key=api_key,
            system_prompt=scenario.customer_prompt,
            transcript=transcript,
            speaker="CUSTOMER",
            model=model,
            temperature=0.65,
            max_tokens=160,
        )
        if customer_reply == "[END]":
            break
        transcript.append({"role": "user", "content": customer_reply})

    return transcript


def _format_transcript(transcript: List[Dict[str, str]]) -> str:
    lines: List[str] = []
    for index, item in enumerate(transcript, start=1):
        speaker = "CUSTOMER" if item["role"] == "user" else "AGENT"
        lines.append(f"{index:02d}. {speaker}: {item['content']}")
    return "\n".join(lines)


async def _generate_next_turn(
    provider: UniAPIProvider,
    *,
    api_key: str,
    system_prompt: str,
    transcript: List[Dict[str, str]],
    speaker: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    transcript_blob = _format_transcript(transcript) if transcript else "(start of chat)"
    task_prompt = (
        f"Conversation so far:\n{transcript_blob}\n\n"
        f"Write only the next {speaker} message.\n"
        "Do not write both sides.\n"
        "Do not add a speaker label.\n"
        "Keep it to one natural WhatsApp message.\n"
        "Return a complete message, not a fragment.\n"
        "Do not cut off mid-sentence or mid-number."
    )
    try:
        return await _generate_text(
            provider,
            api_key=api_key,
            system_prompt=system_prompt,
            transcript=[{"role": "user", "content": task_prompt}],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception:
        if speaker == "CUSTOMER":
            return "[END]"
        raise


def _extract_json_block(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("```")).strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"raw_text": raw}


async def _judge_transcripts(
    provider: UniAPIProvider,
    *,
    api_key: str,
    scenario: Scenario,
    model: str,
    baseline: List[Dict[str, str]],
    skilled: List[Dict[str, str]],
) -> Dict[str, Any]:
    judge_prompt = f"""You are evaluating two WhatsApp sales transcripts for human conversational quality.

Scenario:
{scenario.description}

Score each transcript from 1 to 10 on:
- human_naturalness
- politeness
- pressure_control
- topic_following
- passive_aggressive_risk (10 means low risk, 1 means high risk)

Then decide a winner.

Return strict JSON with keys:
baseline_scores, skilled_scores, winner, summary

Keep summary to one short sentence.

Transcript A (baseline):
{_format_transcript(baseline)}

Transcript B (with human skill):
{_format_transcript(skilled)}
"""

    result = await _generate_text(
        provider,
        api_key=api_key,
        system_prompt="Return strict JSON only. No markdown.",
        transcript=[{"role": "user", "content": judge_prompt}],
        model=model,
        temperature=0.2,
        max_tokens=320,
    )
    return _extract_json_block(result)


async def _main() -> int:
    args = _parse_args()
    api_key = _resolve_api_key(args)
    model = _normalize_model_name(args.model)
    scenario = SCENARIOS[args.scenario]

    provider = UniAPIProvider(api_key=api_key, default_model=model, default_schema="gemini_native")
    try:
        baseline_transcript = await _run_single_simulation(
            provider,
            api_key=api_key,
            scenario=scenario,
            model=model,
            turns=args.turns,
            use_skill=False,
        )
        skilled_transcript = await _run_single_simulation(
            provider,
            api_key=api_key,
            scenario=scenario,
            model=model,
            turns=args.turns,
            use_skill=True,
        )

        result: Dict[str, Any] = {
            "model": model,
            "scenario": {
                "id": scenario.scenario_id,
                "description": scenario.description,
                "opener": scenario.opener,
            },
            "baseline_transcript": baseline_transcript,
            "skilled_transcript": skilled_transcript,
        }

        if not args.no_judge:
            result["judge"] = await _judge_transcripts(
                provider,
                api_key=api_key,
                scenario=scenario,
                model=model,
                baseline=baseline_transcript,
                skilled=skilled_transcript,
            )

        print(f"Scenario: {scenario.scenario_id}")
        print(f"Model: {model}")
        print("\n=== BASELINE ===")
        print(_format_transcript(baseline_transcript))
        print("\n=== WITH HUMAN SKILL ===")
        print(_format_transcript(skilled_transcript))
        if result.get("judge"):
            print("\n=== JUDGE ===")
            print(json.dumps(result["judge"], ensure_ascii=False, indent=2))

        output_path = str(args.output or "").strip()
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\nSaved JSON report to: {path}")
        return 0
    finally:
        await provider.http_client.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
