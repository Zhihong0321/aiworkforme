"""
MODULE: LLM Ports
PURPOSE: App-layer contracts for LLM execution abstractions.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, Sequence


class LLMResponsePort(Protocol):
    content: Optional[str]
    provider_info: Optional[Dict[str, Any]]
    usage: Optional[Dict[str, Any]]


class LLMRouterPort(Protocol):
    async def execute(
        self,
        *,
        task: Any,
        messages: Sequence[Dict[str, Any]],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponsePort: ...
