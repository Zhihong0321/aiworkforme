# Architecture Decisions

## [ADR-001] Layered Monolithic Structure
- **Context**: The previous codebase was flat and files like `main.py` were growing too large (600+ lines).
- **Decision**: Adopt a Clean Architecture Monolith.
- **Consequence**: Better discoverability for AI agents and human developers; reduced merge conflicts.

## [ADR-002] SQLModel Split by Domain
- **Context**: `models.py` (~400 lines) mixed all concepts.
- **Decision**: Split into `user_models.py`, `agent_models.py`, etc.
- **Consequence**: Easier to update specific domains without impacting others.

## [ADR-003] Infrastructure-Managed Bootstrap
- **Context**: `main.py` was cluttered with migration and seeding logic.
- **Decision**: Move logic to `src/infra`.
- **Consequence**: `main.py` remains a thin entry point for the web server.
