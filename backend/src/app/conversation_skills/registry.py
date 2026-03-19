from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from .loader import load_skills
from .types import ConversationSkill, ConversationSkillContext


class ConversationSkillRegistry:
    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
        self._skills: List[ConversationSkill] = []
        self.refresh()

    def refresh(self) -> None:
        self._skills = load_skills(self.skills_dir)

    def resolve(self, ctx: ConversationSkillContext) -> List[ConversationSkill]:
        task_kind = str(ctx.task_kind.value)
        channel = str(ctx.channel or "").strip().lower()
        matches: List[ConversationSkill] = []
        for skill in self._skills:
            meta = skill.meta
            if not meta.enabled:
                continue
            if meta.applies_to_task_kinds and task_kind not in meta.applies_to_task_kinds:
                continue
            if meta.applies_to_channels:
                normalized_channels = [item.strip().lower() for item in meta.applies_to_channels]
                if "*" not in normalized_channels and channel not in normalized_channels:
                    continue
            matches.append(skill)
        return sorted(matches, key=lambda item: (item.meta.priority, item.meta.skill_id))


@lru_cache(maxsize=1)
def get_default_conversation_skill_registry() -> ConversationSkillRegistry:
    skills_dir = Path(__file__).resolve().parent / "skills"
    return ConversationSkillRegistry(skills_dir=skills_dir)
