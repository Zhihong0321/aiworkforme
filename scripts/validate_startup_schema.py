#!/usr/bin/env python3
"""
CI/Deploy guard: verify required runtime schema is present before serving traffic.
"""
import json
import os
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    backend_root = repo_root / "backend"
    sys.path.insert(0, str(backend_root))

    try:
        from src.infra.database import engine
        from src.infra.schema_checks import evaluate_message_schema_compat
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"import_failure: {exc}"}))
        return 2

    result = evaluate_message_schema_compat(engine)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
