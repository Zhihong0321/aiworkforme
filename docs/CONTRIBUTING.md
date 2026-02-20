# Contributing Safely

## Workflow

1. Keep behavior stable: refactor mechanically first, change behavior second.
2. Place code in the correct layer before adding logic.
3. Keep files focused (target 150-300 lines, hard max 500).
4. Add or update tests for critical paths touched.
5. Update `docs/MODULE_INDEX.md` and `docs/DECISIONS.md` for non-trivial changes.

## Layer Rules

- Never put DB/network calls in `domain`.
- Avoid framework objects in `app`/`domain`.
- Keep API routers thin; orchestration belongs in `src/app`.
- Add new external integrations behind `ports` + `adapters`.

## Required Checks

From repo root:

```bash
cd backend
.venv/bin/python -m pytest
```

If your environment has tooling installed:

```bash
cd backend
ruff check .
RUN_LIVE_TESTS=1 .venv/bin/python -m pytest tests/test_t7_reliability_live.py tests/test_m7_observability_live.py
```

## Naming and Consistency

- One concept = one name across modules.
- Prefer explicit names (`workspace_id`, `tenant_id`) over abbreviations.
- Avoid generic `utils` growth; promote cohesive helpers into dedicated modules.
