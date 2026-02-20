# Architecture: Strict SoC Monolith

## Layering and Folder Structure

```text
backend/
  main.py                      # Thin framework entrypoint
  src/
    app/                       # Use-cases + orchestration
    domain/                    # Pure business rules
    ports/                     # Interface contracts
    adapters/                  # IO implementations (api/db/external)
    infra/                     # Wiring, config, migrations, lifecycle
    shared/                    # Tiny cross-cutting primitives
  routers/                     # Legacy API route modules (transitional)
```

## Boundary Rules (Import Direction)

- `domain` imports only `domain` + `shared`.
- `app` imports `domain` + `ports` + `shared`.
- `ports` imports `ports` + `shared`.
- `adapters` imports `ports` + `shared` (legacy exceptions tracked by tests).
- `infra` can import all layers; it performs composition/wiring.
- HTTP handlers stay thin and delegate to `app` logic.

## Responsibility Placement

- Domain logic: `backend/src/domain`.
- Orchestration/use-cases: `backend/src/app`.
- IO and persistence concerns: `backend/src/adapters`.
- Framework/boot/wiring: `backend/src/infra` + thin `backend/main.py`.

## Enforcement

- `backend/tests/test_architecture_boundaries.py` blocks new cross-layer violations.
- Transitional violations are allowlisted and must only decrease over time.
- New modules require file headers and folder README orientation docs.
