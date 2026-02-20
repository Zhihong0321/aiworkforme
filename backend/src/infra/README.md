# `infra` Layer

Purpose: framework glue and application wiring.

Allowed imports: any layer; infra sits at the outer boundary.

Key files:
- `database.py`: engine/session creation.
- `migrations.py`: additive schema migration operations.
- `lifecycle.py`: startup/shutdown orchestration.
- `security.py`: auth primitives.
