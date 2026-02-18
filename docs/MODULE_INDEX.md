# Module Index

## Infrastructure
- `src/infra/database.py`: SQLModel engine and session configuration.
- `src/infra/migrations.py`: Additive multitenant schema migrations.
- `src/infra/seeding.py`: Identity, asset, and script seeding logic.
- `src/infra/security.py`: Password hashing and JWT management.

## Adapters
- `src/adapters/db/agent_models.py`: Agent and Knowledge File models.
- `src/adapters/db/user_models.py`: User and Membership models.
- `src/adapters/db/tenant_models.py`: Tenant and System Setting models.
- `src/adapters/db/chat_models.py`: Chat Session and Message models.
- `src/adapters/db/crm_models.py`: Lead, Workspace, and Strategy models.
- `src/adapters/db/audit_models.py`: Log schemas for audit and security.
- `src/adapters/db/audit_recorder.py`: Helper functions for recording logs.
- `src/adapters/api/dependencies.py`: Unified FastAPI Auth and Provider dependencies.
- `src/adapters/mcp/manager.py`: MCP Server process orchestration.
- `src/adapters/zai/client.py`: OpenAI-compatible LLM client.

## Application
- `src/app/background_tasks.py`: CRM and Maintenance background loops.
- `src/app/runtime/agent_runtime.py`: Core conversation logic.
- `src/app/runtime/crm_agent.py`: Lead lifecycle management.
- `src/app/policy/evaluator.py`: Safety and compliance engine.

## Domain
- `src/domain/entities/enums.py`: Universal enums for Role, Status, and Tiers.

## Shared
- `src/shared/exceptions.py`: Application-wide base error classes.
