# `adapters` Layer

Purpose: concrete IO adapters (DB/API/external clients).

Allowed imports: `src.ports`, `src.shared` primarily. Transitional exceptions are documented and tested.

Key folders:
- `api/`: FastAPI dependencies and wiring helpers.
- `db/`: SQLModel tables and persistence mappings.
- `mcp/`, `zai/`: external runtime clients.
