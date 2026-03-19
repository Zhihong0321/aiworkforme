from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConversationTaskKind(str, Enum):
    CONVERSATION = "conversation"
    INITIAL_OUTREACH = "initial_outreach"
    FOLLOWUP_GENERATION = "followup_generation"
    VOICE_NOTE_GENERATION = "voice_note_generation"
    CRM_ANALYSIS = "crm_analysis"


@dataclass(frozen=True)
class ConversationSkillMeta:
    skill_id: str
    version: str
    enabled: bool
    priority: int
    applies_to_task_kinds: List[str]
    applies_to_channels: List[str]
    description: str


@dataclass(frozen=True)
class ConversationSkill:
    meta: ConversationSkillMeta
    body: str
    yaml_path: Path
    md_path: Path


@dataclass(frozen=True)
class ConversationSkillContext:
    task_kind: ConversationTaskKind
    channel: Optional[str] = None
    agent_id: Optional[int] = None
    tenant_id: Optional[int] = None


@dataclass(frozen=True)
class ComposedConversationPrompt:
    system_prompt: str
    applied_skills: List[Dict[str, Any]] = field(default_factory=list)
    debug_trace: Dict[str, Any] = field(default_factory=dict)
