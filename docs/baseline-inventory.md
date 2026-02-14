# Baseline Architecture Inventory: Eternalgy Prototype

This document provides a comprehensive inventory of the existing Eternalgy prototype assets and their disposition as we transition to the Masterplan MVP.

## Backend Architecture (FastAPI)

The backend is built with FastAPI and handles agent interactions, MCP management, and database persistence.

### Core Modules
| Final Path | Asset | Decision | Extraction Action |
| --- | --- | --- | --- |
| `backend/main.py` | App Entrypoint | REFACTOR | Keep bootstrap logic, replace startup seeding with migration-safe initialization. |
| `backend/database.py` | DB Engine/Session | REFACTOR | Keep SQLAlchemy wiring, integrate migration controls. |
| `backend/models.py` | SQL Models | REWRITE | Prototype models are agent-centric. Replace with Workspace/Lead/Policy/Strategy models. |
| `backend/dependencies.py` | DI Injectables | REFACTOR | Keep DI pattern, shift singletons to workspace-aware factories. |
| `backend/zai_client.py` | AI Client | REWRITE | Hardcoded model assumptions. Replace with UniAPI + Gemini provider abstraction. |
| `backend/mcp_manager.py` | MCP Orchestrator | REFACTOR | Keep process lifecycle, add workspace allowlists and tool budgets. |

### API Routes
| Final Path | Intent | Decision | Extraction Action |
| --- | --- | --- | --- |
| `backend/routers/chat.py` | Chat Execution | REFACTOR | Keep tool loop, wrap in pre/post policy gates. |
| `backend/routers/mcp.py` | MCP CRUD | REFACTOR | Keep endpoint shapes, add tenant scoping and auth. |
| `backend/routers/knowledge.py`| File Management | REFACTOR | Keep handlers, move to strategy-linked retrieval contracts. |
| `backend/routers/agents.py` | Agent CRUD | REWRITE | Replace with Lead/Outreach lifecycle APIs. |
| `backend/routers/settings.py`| App Settings | REFACTOR | Redesign for secure provider credential management. |

### MCP Servers
| Final Path | Capability | Decision | Extraction Action |
| --- | --- | --- | --- |
| `backend/mcp_servers/knowledge_retrieval.py` | Local RAG | REWRITE | Upgrade to pgvector + embeddings + token budgeting. |
| `backend/mcp_servers/billing_mcp.py` | Demo Billing | DROP | Irrelevant to WhatsApp lead focus. |

## Frontend Architecture (Vue 3 + Vite)

The frontend is a playground/admin dashboard for managing prototype agents and MCPs.

### Core Structure
| Path | Component Type | Status | Strategy |
| --- | --- | --- | --- |
| `frontend/src/router/index.js` | Routing | REWRITE | Map to Inbox, Leads, Strategy, Knowledge, Analytics. |
| `frontend/src/views/Chat.vue` | Conversation UI | REFACTOR | Extract timeline/composer logic for Inbox. |
| `frontend/src/views/KnowledgeVault.vue`| RAG Admin | REFACTOR | Re-implement as Knowledge page contracts. |
| `frontend/src/views/Dashboard.vue` | Dashboard | DROP | Replaced by Masterplan page model. |
| `frontend/src/components/ui/*` | UI Primitives | REFACTOR | Align with loading/empty/ready/error contract states. |

## Infrastructure & Tests
* **Multi-stage Dockerfile**: REFACTOR for unified deployment.
* **Docker Compose**: REFACTOR for multi-service support (Database, Queue, App).
* **MCP Validation Tests**: REFACTOR for workspace isolation and policy-bound execution.

## Summary of Debt to be Addressed
1. **No Workspace Isolation**: All data is currently global/single-tenant.
2. **No Policy Layer**: Messages send immediately without safety checks.
3. **Lexical Retrieval**: Knowledge search lacks semantic depth and token governance.
4. **Agent-Centric Domain**: Schema focuses on "AI agents" rather than "lead conversion outcomes".
