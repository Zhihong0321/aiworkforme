from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .types import ConversationSkill, ConversationSkillMeta


def _parse_scalar(raw_value: str) -> Any:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered.isdigit():
        try:
            return int(lowered)
        except ValueError:
            return value
    return value


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    current_list_key = None

    for raw_line in str(text or "").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- ") and current_list_key:
            data.setdefault(current_list_key, []).append(_parse_scalar(stripped[2:]))
            continue

        current_list_key = None
        if ":" not in line:
            continue

        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if not value:
            data[key] = []
            current_list_key = key
            continue
        data[key] = _parse_scalar(value)

    return data


def load_skill(meta_path: Path) -> ConversationSkill:
    yaml_path = Path(meta_path)
    md_path = yaml_path.with_suffix(".md")
    if not yaml_path.exists():
        raise FileNotFoundError(f"Conversation skill metadata not found: {yaml_path}")
    if not md_path.exists():
        raise FileNotFoundError(f"Conversation skill body not found: {md_path}")

    meta_raw = _parse_simple_yaml(yaml_path.read_text(encoding="utf-8"))
    body = md_path.read_text(encoding="utf-8").strip()
    meta = ConversationSkillMeta(
        skill_id=str(meta_raw.get("id") or yaml_path.stem).strip(),
        version=str(meta_raw.get("version") or "1").strip(),
        enabled=bool(meta_raw.get("enabled", True)),
        priority=int(meta_raw.get("priority", 100) or 100),
        applies_to_task_kinds=[str(item).strip() for item in list(meta_raw.get("applies_to_task_kinds") or []) if str(item).strip()],
        applies_to_channels=[str(item).strip() for item in list(meta_raw.get("applies_to_channels") or []) if str(item).strip()],
        description=str(meta_raw.get("description") or "").strip(),
    )
    return ConversationSkill(meta=meta, body=body, yaml_path=yaml_path, md_path=md_path)


def load_skills(skills_dir: Path) -> List[ConversationSkill]:
    root = Path(skills_dir)
    skills: List[ConversationSkill] = []
    for meta_path in sorted(root.glob("*.yaml")):
        skills.append(load_skill(meta_path))
    return skills
