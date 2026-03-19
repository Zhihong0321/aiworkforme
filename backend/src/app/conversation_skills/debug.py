from __future__ import annotations

from typing import Any, Dict

from .types import ComposedConversationPrompt


def build_conversation_skill_trace(composed: ComposedConversationPrompt) -> Dict[str, Any]:
    return dict(composed.debug_trace or {})
