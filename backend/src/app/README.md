# `app` Layer

Purpose: orchestrates domain logic and use-cases.

Allowed imports: `src.domain`, `src.ports`, `src.shared` (transitional exceptions are tracked in tests).

Key files:
- `background_tasks_*.py`: long-running orchestrators.
- `runtime/`: conversation and CRM workflows.
- `policy/evaluator.py`: policy decision logic.
