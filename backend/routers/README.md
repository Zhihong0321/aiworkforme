# `backend/routers` (Legacy API Layer)

Purpose: transitional FastAPI endpoint modules while logic is moved into `backend/src` layers.

Allowed imports: `src.app`, `src.adapters`, `src.infra`, `src.shared`; avoid domain logic in route modules.

Key files:
- `platform.py`: thin composition for platform admin subrouters.
- `platform_*_routes.py`: focused platform endpoint modules.
- `messaging.py`: messaging composition router.
- `messaging_whatsapp_routes.py`: WhatsApp session lifecycle endpoints.
- `messaging_whatsapp_import_routes.py`: WhatsApp conversation import endpoint.
- `messaging_core_routes.py`: outbound/inbound/thread dispatch endpoints.
- `messaging_mvp_routes.py`: MVP operational/debug/simulation endpoints.
- `messaging_runtime.py`: shared runtime operations for messaging routes.
- `messaging_schemas.py`: messaging request/response DTOs.
- `messaging_helpers.py`: compatibility facade for helper modules.
- `messaging_helpers_validation.py`: messaging validation/session/thread helpers.
- `messaging_helpers_payload.py`: provider payload parsing/normalization helpers.
- `ai_crm.py`: AI CRM composition router.
- `ai_crm_routes.py`: AI CRM HTTP handlers.
- `ai_crm_runtime.py`: AI CRM scan/trigger/background orchestration.
- `ai_crm_helpers.py`: AI CRM helper logic.
- `ai_crm_schemas.py`: AI CRM request/response DTOs.
