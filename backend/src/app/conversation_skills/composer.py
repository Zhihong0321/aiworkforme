from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from .registry import ConversationSkillRegistry
from .types import ComposedConversationPrompt, ConversationSkillContext, ConversationTaskKind


def _render_section(title: str, body: str) -> str:
    heading = str(title or "").strip()
    content = str(body or "").strip()
    if not content:
        return ""
    if not heading:
        return content
    return f"--- {heading} ---\n{content}"


def compose_conversation_prompt(
    *,
    registry: ConversationSkillRegistry,
    base_prompt: str,
    task_kind: ConversationTaskKind,
    channel: Optional[str],
    agent_id: Optional[int],
    tenant_id: Optional[int],
    strategy_prompt: Optional[str] = None,
    extra_sections: Optional[Sequence[Tuple[str, str]]] = None,
) -> ComposedConversationPrompt:
    ctx = ConversationSkillContext(
        task_kind=task_kind,
        channel=channel,
        agent_id=agent_id,
        tenant_id=tenant_id,
    )
    matched_skills = registry.resolve(ctx)
    sections: List[str] = []

    base = str(base_prompt or "").strip()
    if base:
        sections.append(base)

    strategy = str(strategy_prompt or "").strip()
    if strategy:
        sections.append(_render_section("STRATEGY", strategy))

    for title, body in list(extra_sections or []):
        rendered = _render_section(title, body)
        if rendered:
            sections.append(rendered)

    applied = []
    for skill in matched_skills:
        sections.append(
            _render_section(
                f"PLATFORM CONVERSATION SKILL: {skill.meta.skill_id} v{skill.meta.version}",
                skill.body,
            )
        )
        applied.append(
            {
                "id": skill.meta.skill_id,
                "version": skill.meta.version,
                "priority": skill.meta.priority,
            }
        )

    if matched_skills:
        sections.append(
            "If any earlier instruction conflicts with the conversation behavior rules above, "
            "follow the conversation behavior rules above for customer-facing replies."
        )

    system_prompt = "\n\n".join(section for section in sections if section).strip()
    debug_trace = {
        "task_kind": task_kind.value,
        "channel": channel,
        "agent_id": agent_id,
        "tenant_id": tenant_id,
        "skills_dir": str(registry.skills_dir),
        "applied": applied,
        "section_count": len([section for section in sections if section]),
    }
    return ComposedConversationPrompt(
        system_prompt=system_prompt,
        applied_skills=applied,
        debug_trace=debug_trace,
    )
