# Prototype Extraction Matrix (Eternalgy-MCP-RAG -> Masterplan Build)

## Scope
This matrix evaluates only prototype code in `/Users/ganzhihong/Documents/aiworkfor.me/Eternalgy-MCP-RAG`.
Product direction is controlled only by `/Users/ganzhihong/Documents/aiworkfor.me/MASTERPLAN.MD`.

Decision labels:
- `KEEP`: carry over with minimal edits.
- `REFACTOR`: preserve core logic, change interfaces/schema/guards.
- `REWRITE`: rebuild for Masterplan requirements; prototype is reference only.
- `DROP`: do not migrate.

## Backend Matrix
| Prototype Asset | Decision | Why | Extraction Action |
|---|---|---|---|
| `backend/routers/chat.py` | `REFACTOR` | Solid tool-call loop and message persistence flow, but no safety floor, lead lifecycle, workspace scope, or outbound policy gate. | Keep loop structure, rebind to `Workspace/Lead/PolicyDecision`, add pre/post policy checks and takeover/suppression gates. |
| `backend/mcp_manager.py` | `REFACTOR` | Useful stdio MCP orchestration, timeout, and tool cache. Missing workspace allowlist, tool-call budget, and strict fallback policy. | Keep process/session patterns; add workspace-level tool allowlist, max tool-call caps, and hard fail-fast contract. |
| `backend/routers/mcp.py` | `REFACTOR` | CRUD/start/stop/list/call paths are reusable. Needs tenant scoping, authz, and stronger audit/security controls. | Keep endpoint shape patterns, rebuild with workspace ownership, audit log, and policy hooks. |
| `backend/main.py` | `REFACTOR` | Router wiring and health checks are reusable skeleton. Startup seeding and defaults are prototype-specific. | Keep app bootstrap pattern; replace startup logic with migration-safe boot and workspace-aware service initialization. |
| `backend/database.py` | `REFACTOR` | Simple engine/session pattern is reusable. No tenant/session controls and no migration governance integration. | Keep basic DB wiring style; integrate migration controls and environment-specific safety checks. |
| `backend/dependencies.py` | `REFACTOR` | Dependency injection pattern is useful, but singleton assumptions are too loose for multi-tenant runtime controls. | Keep DI style; replace with provider/policy/tenant-aware factories. |
| `backend/routers/settings.py` | `REFACTOR` | API-key management flow is useful but provider-specific and not workspace-aware. | Keep endpoint pattern, redesign for secure provider credential management and secret handling. |
| `backend/routers/knowledge.py` | `REFACTOR` | Basic file metadata update/delete paths are useful. Missing workspace boundaries and retrieval contracts. | Keep CRUD handler style; move to Masterplan knowledge contracts and strategy-linked source control. |
| `backend/models.py` | `REWRITE` | Prototype schema is agent-centric; Masterplan requires workspace/lead/stage/tag/policy/budget strategy domain. | Replace with Masterplan domain entities and enums (`LeadStage`, `LeadTag`, `BudgetTier`, etc.). |
| `backend/routers/agents.py` | `REWRITE` | Endpoint set is for prototype agent CRUD, not lead/outreach lifecycle. | Rebuild around Masterplan APIs and lifecycle transitions. |
| `backend/zai_client.py` | `REWRITE` | Hardcoded Z.ai base/model assumptions conflict with UniAPI + Gemini runtime target. | Build provider abstraction layer; add UniAPI transport, model routing, cost tiering, and traceability. |
| `backend/mcp_servers/knowledge_retrieval.py` | `REWRITE` | Retrieval is lexical scoring and globally scoped; Masterplan needs strategy-linked retrieval + embeddings + token budgeting. | Rebuild retrieval service with embedding/vector path, source priority, and scoped audit trace. |
| `backend/mcp_servers/billing_mcp.py` | `DROP` | Domain-specific demo tooling not relevant to WhatsApp lead automation MVP. | Exclude from migration. |
| `backend/mcp_servers/billing-mcp-server-v2/*` | `DROP` | Prototype-specific billing utility, no Masterplan alignment. | Exclude from migration. |
| `backend/simple_mcp_server.py` | `DROP` | Sample tool server only. | Do not carry into production app. |

## Frontend Matrix
| Prototype Asset | Decision | Why | Extraction Action |
|---|---|---|---|
| `frontend/src/components/ui/*` | `REFACTOR` | Reusable primitive component patterns exist, but styles/states are not mapped to Masterplan component contracts. | Reuse selective primitives, align props/states to `loading/empty/ready/error/suppressed` contract model. |
| `frontend/src/composables/theme.js` | `KEEP` | Small, clean utility for persistent theme state. | Keep if frontend stack remains Vue; otherwise translate behavior to chosen stack. |
| `frontend/src/router/index.js` | `REWRITE` | Route map is prototype admin/test layout; Masterplan requires `Inbox/Leads/Strategy/Knowledge/Analytics`. | Rebuild route map to Masterplan page architecture. |
| `frontend/src/views/Dashboard.vue` | `DROP` | Prototype operations dashboard conflicts with required page model. | Replace with Masterplan pages. |
| `frontend/src/views/Agents.vue` | `DROP` | Agent CRUD UI not the target control-plane model. | Replace with `Leads` + `Strategy` contracts. |
| `frontend/src/views/Chat.vue` | `REFACTOR` | Message timeline/composer interaction patterns are useful for `Inbox`. | Extract conversation timeline/composer behavior into `Inbox` components with policy badges and action bar hooks. |
| `frontend/src/views/Tester.vue` | `DROP` | Playground/testing surface only. | Exclude from product UI. |
| `frontend/src/views/Mcps.vue` | `DROP` | Internal MCP admin page is not in MVP core pages. | Exclude from operator UI; keep only as internal debug tooling if needed outside product. |
| `frontend/src/views/Settings.vue` | `DROP` | Prototype settings surface does not match Masterplan controls. | Rebuild settings scope under strategy/cost/policy controls where needed. |
| `frontend/src/views/KnowledgeVault.vue` | `REFACTOR` | Contains useful knowledge management interaction patterns, but contract/state/telemetry are incomplete. | Keep interaction ideas, re-implement as Masterplan `Knowledge` page contracts. |
| `frontend/src/views/ComponentLibrary.vue` | `DROP` | Design sandbox only. | Exclude from product. |
| `frontend/src/components/TopNav.vue` | `REFACTOR` | Basic nav shell is reusable. | Rewire nav to Masterplan pages and control-plane semantics. |

## Tests and Quality Matrix
| Prototype Asset | Decision | Why | Extraction Action |
|---|---|---|---|
| `backend/test_mcp_validation.py` | `REFACTOR` | Useful MCP endpoint test scaffolding. Contains minor assertion drift and no tenant/policy coverage. | Keep structure, expand to workspace isolation, timeout/fallback, and policy-bound tool execution tests. |
| `backend/test_full_scenario.py` | `DROP` | Manual script-style scenario, environment-coupled, not CI-grade contract test. | Replace with deterministic integration tests. |
| `backend/test_billing_scenario.py` | `DROP` | Billing-specific and not product-aligned. | Exclude. |
| `test_prod_chat.py` | `DROP` | Hardcoded environment target; not a reusable test harness. | Exclude. |
| `full-test.md` and prototype test docs | `DROP` | Outdated test narrative relative to Masterplan gates. | Replace with milestone-gated test specs. |

## Infra and Repository Hygiene Matrix
| Prototype Asset | Decision | Why | Extraction Action |
|---|---|---|---|
| `Dockerfile` (root multi-stage) | `REFACTOR` | Good starting point for single-image deployment. Needs runtime hardening and service alignment. | Keep multi-stage pattern, update for final app topology and security controls. |
| `backend/Dockerfile` | `DROP` | Duplicates deployment intent and creates maintenance split. | Standardize on one production Docker strategy. |
| `docker-compose.yml` | `REFACTOR` | Useful local orchestration starter. Needs service updates for new architecture and queues/jobs. | Keep as local dev baseline, update services and health gates. |
| `.env.example` | `REFACTOR` | Useful skeleton but provider/setting names are prototype-specific. | Replace with Masterplan-aligned env contract. |
| `backend/frontend-dist/*` | `DROP` | Build artifacts should not be treated as source. | Remove from extraction scope. |
| `frontend/archive/*` | `DROP` | Historical/legacy prototype files. | Exclude. |
| `backend/*.db` (`gen_schema.db`, `test.db`) | `DROP` | Local state artifacts only. | Exclude from migration/source. |
| `bill-2025.json`, `payload.json`, `image.png` | `DROP` | Prototype/demo assets not tied to Masterplan MVP scope. | Exclude unless explicitly needed for docs only. |

## Non-Code Prototype Docs Matrix
| Prototype Asset | Decision | Why | Extraction Action |
|---|---|---|---|
| `build-plan.md`, `frontend-buildplan.md`, `knowledge-mcp-task-plan.md` | `DROP` | Product direction source is Masterplan only. | Do not use as build authority. |
| `DOC_*` and `WORKING_WITH_MCP_SERVER.md` | `DROP` (as authority) / `REFACTOR` (as technical notes) | Some technical notes are useful, but many references are stale or architecture-divergent. | Use only for isolated technical hints after code verification; do not treat as requirement source. |

## Extraction Priority (Execution Order)
1. `REFACTOR` extraction first: `chat.py`, `mcp_manager.py`, `mcp.py`, selected UI primitives.
2. Domain `REWRITE` second: schema, lifecycle, policy engine, CRM loops.
3. UI `REWRITE/REFACTOR` third: Masterplan core 5 pages and contracts.
4. `DROP` cleanup in parallel: legacy docs/artifacts/demo assets.

## Hard Rule During Extraction
If any prototype behavior conflicts with `/Users/ganzhihong/Documents/aiworkfor.me/MASTERPLAN.MD`, Masterplan wins and prototype behavior is discarded.
