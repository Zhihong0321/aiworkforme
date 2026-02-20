# Architecture Decisions

## ADR-2026-02-20-01: Thin Entrypoint + Explicit Wiring

Decision:
- Refactor `backend/main.py` to composition-only.
- Move lifecycle orchestration into `backend/src/infra/lifecycle.py`.
- Move router registration into `backend/src/adapters/api/router_registry.py`.
- Move status endpoints into `backend/src/adapters/api/status_routes.py`.

Why:
- Keeps framework wiring separate from startup workflows.
- Reduces cognitive load and cross-session agent onboarding time.
- Makes behavior-preserving refactors safer and more mechanical.

Tradeoff:
- Adds more files, but each file has a single responsibility.

## ADR-2026-02-20-02: Boundary Enforcement with Transitional Allowlist

Decision:
- Add `backend/tests/test_architecture_boundaries.py`.
- Enforce no new cross-layer imports while temporarily allowlisting legacy violations.

Why:
- Enables strict directionality incrementally without risky rewrites.
- Prevents architecture drift during concurrent agent sessions.

Tradeoff:
- Some existing violations remain until follow-up extraction work is done.

## ADR-2026-02-20-03: Folder-Level AI Orientation Docs

Decision:
- Add README files to `backend/src` and each layer folder.

Why:
- Faster orientation and safer edits for human + AI contributors.
- Makes boundary rules searchable and local to implementation.
