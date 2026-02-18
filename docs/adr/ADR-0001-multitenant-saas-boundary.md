# ADR-0001: Multi-Tenant SaaS Boundary and Role Model
Date: 2026-02-16
Status: Accepted
Owners: Platform Engineering
Related: `MASTERPLAN.MD`, `build-plan-multi-tenant.md`, `test-plan-multi-tenant.md`

## Context
The pre-refactor system mixed tenant and platform concerns, lacked strict identity context on every request, and allowed global access patterns on data paths that must be tenant scoped.

To launch as SaaS safely, the architecture must define hard boundaries for identity, tenancy, routes, and operator actions.

## Decision
1. Role model:
- `platform_admin`: controls tenants/users/platform keys only.
- `tenant_admin` and `tenant_user`: operate only within their tenant context.

2. Request identity contract:
- All protected routes require authenticated caller context.
- Tenant routes require a resolved tenant context (`token tenant_id` or `X-Tenant-Id`) and tenant membership.
- Platform routes require `platform_admin`.

3. API boundary model:
- Platform control plane: `/api/v1/platform/*`.
- Tenant app plane: `/api/v1/*` routes guarded by tenant dependency.
- Legacy `/v1/*` compatibility kept only for explicitly guarded adapters with deprecation headers.

4. Data ownership model:
- Tenant-owned tables carry `tenant_id` and enforce database-level non-null + FK constraints.
- Platform-global tables remain outside tenant ownership domain.

5. Audit and security telemetry:
- Admin operations are immutable in `et_admin_audit_logs`.
- Authorization denials are persisted in `et_security_events` with endpoint/method/status/reason.

6. Key management policy:
- API key management is platform-admin only for MVP.
- Read APIs return masked keys; raw secret is never returned after write.

## Consequences
- Tenant isolation is enforceable at both application and database layers.
- Platform operators can observe denial attempts and export audit trails.
- Remaining legacy paths are explicitly bounded and observable.

## Migration and Rollback Strategy
1. Additive schema and route hardening first.
2. Backfill tenant ownership to bootstrap tenant.
3. Enforce strict guards and reject unscoped access.
4. Keep compatibility adapter only where needed, then sunset.

Rollback:
- Revert to previous image + schema snapshot.
- Re-enable compatibility flags/routes where necessary.
- Preserve audit/security tables as immutable history.

## Sign-off
- Architecture decision accepted for execution against milestones M1-M8.
- No unresolved blocker recorded for M0 at this time.
