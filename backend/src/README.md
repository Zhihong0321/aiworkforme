# `src` Layered Monolith

Purpose: canonical implementation for the backend monolith.

Allowed direction: dependencies point inward (`adapters/infra` -> `app` -> `domain/ports/shared`).

Key folders:
- `app/`: orchestration and use-cases.
- `domain/`: pure business entities/policies.
- `ports/`: abstraction interfaces.
- `adapters/`: IO implementations and API adapters.
- `infra/`: framework/config/wiring/migrations.
- `shared/`: tiny cross-cutting primitives.
