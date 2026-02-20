"""
MODULE: Architecture Boundary Tests
PURPOSE: Enforce import direction rules for the strict SoC monolith.
DOES: Fail on newly introduced cross-layer imports that break boundaries.
DOES NOT: Enforce full cleanup of legacy violations in one step.
INVARIANTS: Existing behavior is preserved while architectural debt is tracked.
SAFE CHANGE: Remove entries from the allowlist as modules are refactored.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"

LAYER_ALLOW_IMPORTS: dict[str, set[str]] = {
    "domain": {"domain", "shared"},
    "ports": {"ports", "shared"},
    "shared": {"shared"},
    "app": {"app", "domain", "ports", "shared"},
    "adapters": {"adapters", "ports", "shared"},
    "infra": {"infra", "adapters", "app", "domain", "ports", "shared"},
}

# Transitional allowlist of existing violations in the current codebase.
# Policy: only shrink this set over time; new violations are not allowed.
KNOWN_VIOLATIONS: set[tuple[str, str, str]] = {
    ("adapters/api/status_routes.py", "adapters", "infra"),
    ("adapters/api/dependencies.py", "adapters", "domain"),
    ("adapters/api/dependencies.py", "adapters", "infra"),
    ("adapters/db/tenant_models.py", "adapters", "domain"),
    ("adapters/db/user_models.py", "adapters", "domain"),
    ("app/background_tasks_ai_crm.py", "app", "infra"),
    ("app/background_tasks_inbound.py", "app", "adapters"),
    ("app/background_tasks_inbound.py", "app", "infra"),
    ("app/background_tasks_messaging.py", "app", "infra"),
    ("app/policy/evaluator.py", "app", "adapters"),
    ("app/runtime/agent_runtime.py", "app", "adapters"),
    ("app/runtime/agent_runtime.py", "app", "infra"),
    ("app/runtime/context_builder.py", "app", "adapters"),
    ("app/runtime/crm_agent.py", "app", "adapters"),
    ("app/runtime/knowledge_processor.py", "app", "infra"),
    ("app/runtime/memory_service.py", "app", "adapters"),
    ("app/runtime/memory_service.py", "app", "infra"),
    ("app/runtime/rag_service.py", "app", "adapters"),
}


def _iter_src_files() -> Iterable[Path]:
    return sorted(SRC_ROOT.rglob("*.py"))


def _layer_for(path: Path) -> str:
    return path.relative_to(SRC_ROOT).parts[0]


def _imported_src_layers(tree: ast.AST) -> Iterable[str]:
    seen: set[str] = set()
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(name.name for name in node.names)

        for module in modules:
            if module.startswith("src."):
                parts = module.split(".")
                if len(parts) >= 2:
                    layer = parts[1]
                    if layer not in seen:
                        seen.add(layer)
                        yield layer


def test_no_new_cross_layer_imports() -> None:
    unexpected: list[tuple[str, str, str]] = []

    for file_path in _iter_src_files():
        layer = _layer_for(file_path)
        if layer not in LAYER_ALLOW_IMPORTS:
            continue

        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        rel = str(file_path.relative_to(SRC_ROOT))

        for target_layer in _imported_src_layers(tree):
            if target_layer not in LAYER_ALLOW_IMPORTS:
                continue
            if target_layer in LAYER_ALLOW_IMPORTS[layer]:
                continue

            violation = (rel, layer, target_layer)
            if violation not in KNOWN_VIOLATIONS:
                unexpected.append(violation)

    assert not unexpected, (
        "New architecture boundary violations found. "
        "Move logic behind ports/adapters or update layering.\n"
        + "\n".join(sorted(f"- {rel}: {src} -> {dst}" for rel, src, dst in unexpected))
    )
