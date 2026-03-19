from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.app.conversation_skills import (
    ConversationSkillContext,
    ConversationSkillRegistry,
    ConversationTaskKind,
    compose_conversation_prompt,
)
from src.app.conversation_skills.loader import load_skill


def test_load_real_human_base_skill():
    meta_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "app"
        / "conversation_skills"
        / "skills"
        / "human-base.yaml"
    )
    skill = load_skill(meta_path)

    assert skill.meta.skill_id == "human-base"
    assert skill.meta.enabled is True
    assert ConversationTaskKind.CONVERSATION.value in skill.meta.applies_to_task_kinds
    assert "real person" in skill.body


def test_registry_and_composer_apply_human_base_for_conversation_only():
    skills_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "app"
        / "conversation_skills"
        / "skills"
    )
    registry = ConversationSkillRegistry(skills_dir=skills_dir)

    conversation_ctx = ConversationSkillContext(
        task_kind=ConversationTaskKind.CONVERSATION,
        channel="whatsapp",
        agent_id=1,
        tenant_id=1,
    )
    crm_analysis_ctx = ConversationSkillContext(
        task_kind=ConversationTaskKind.CRM_ANALYSIS,
        channel="whatsapp",
        agent_id=1,
        tenant_id=1,
    )

    conversation_skills = registry.resolve(conversation_ctx)
    analysis_skills = registry.resolve(crm_analysis_ctx)

    assert [skill.meta.skill_id for skill in conversation_skills] == ["human-base"]
    assert analysis_skills == []

    composed = compose_conversation_prompt(
        registry=registry,
        base_prompt="Base prompt",
        task_kind=ConversationTaskKind.CONVERSATION,
        channel="whatsapp",
        agent_id=1,
        tenant_id=1,
        strategy_prompt="Talk clearly",
        extra_sections=[("EXTRA", "Some extra section")],
    )

    assert "Base prompt" in composed.system_prompt
    assert "Talk clearly" in composed.system_prompt
    assert "PLATFORM CONVERSATION SKILL: human-base v1" in composed.system_prompt
    assert composed.debug_trace["applied"] == [{"id": "human-base", "version": "1", "priority": 100}]
