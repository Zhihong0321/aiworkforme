"""
MODULE: Test Collection Policy
PURPOSE: Keep default local pytest runs deterministic and offline-safe.
DOES: Skip live tests unless explicitly enabled via environment variable.
DOES NOT: Modify test behavior for non-live test modules.
INVARIANTS: CI/local default `pytest` should not depend on external services.
SAFE CHANGE: Extend skip rules only for clearly integration-only suites.
"""

from __future__ import annotations

import os
from pathlib import Path


def pytest_ignore_collect(collection_path: Path, config) -> bool:  # type: ignore[override]
    run_live = os.getenv("RUN_LIVE_TESTS", "0") == "1"
    if collection_path.name.endswith("_live.py") and not run_live:
        return True
    return False
