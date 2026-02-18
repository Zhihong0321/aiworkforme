# Architecture: Monolith SoC

## System Architecture: Strict SoC Monolith

This project follows a strict **Separation of Concerns (SoC) Monolith** architecture. By centralizing logic into distinct layers, we ensure maximum maintainability and AI-readiness.

## Layering Strategy

1.  **Domain (`/src/domain`)**:
    *   Pure business logic, entities, and enums.
    *   Zero dependencies on external frameworks or adapters.
    *   *Examples: `enums.py`*

2.  **App (`/src/app`)**:
    *   Orchestration, Use Cases, and Background Tasks.
    *   Depends on Domain and Ports.
    *   *Examples: `background_tasks.py`, `runtime/`, `policy/`*

3.  **Ports (`/src/ports`)**:
    *   Abstract interfaces for IO. (To be expanded in Phase 2)

4.  **Adapters (`/src/adapters`)**:
    *   Concrete IO implementations.
    *   `db/`: Model definitions and database-specific helpers.
    *   `api/`: FastAPI dependencies and singleton providers.
    *   `mcp/`, `zai/`: External client implementations.

5.  **Infrastructure (`/src/infra`)**:
    *   Low-level wiring: Database config, Migrations, Seeding, Security.

6.  **Shared (`/src/shared`)**:
    *   Cross-cutting utilities like base exceptions.

## Hard Rules

- **Inward Dependency Rule**: Inner layers (Domain/App) MUST NOT import from outer layers (Adapters/Infra).
- **Single Responsibility**: Every module has one job.
- **Small Files**: Keep files under 200 lines where possible.
- **AI-First Documentation**: Every file has a module header.
