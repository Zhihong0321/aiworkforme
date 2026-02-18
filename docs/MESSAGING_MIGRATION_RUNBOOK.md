# Messaging Migration Runbook

## Purpose
Ensure canonical messaging schema is applied consistently in local Docker and Railway production.

## Source of Truth
- SQL migration file: `backend/sql/messaging_m1_unified_schema.sql`
- Startup runner: `backend/src/infra/migrations.py` -> `apply_sql_migration_file(...)`
- Startup call site: `backend/main.py`

## Local Docker (Current)
Apply manually if needed:

```bash
docker exec -i aiworkforme-db-1 psql -U user -d chatbot_db < backend/sql/messaging_m1_unified_schema.sql
```

Verify:

```bash
docker exec aiworkforme-db-1 psql -U user -d chatbot_db -c "\dt et_*"
docker exec aiworkforme-db-1 psql -U user -d chatbot_db -c "SELECT tgname, tgrelid::regclass FROM pg_trigger WHERE tgname='tr_assign_inbound_thread';"
```

## Railway Production via GitHub Deploy
1. Push code with:
- `backend/sql/messaging_m1_unified_schema.sql`
- startup migration invocation in `backend/main.py`.

2. Redeploy Railway service.

3. On startup, backend auto-applies idempotent SQL migration (PostgreSQL only).

4. Validate from Railway DB console:
- tables exist: `et_channel_sessions`, `et_threads`, `et_messages`, `et_outbound_queue`, `et_thread_insights`
- trigger exists: `tr_assign_inbound_thread` on `et_messages`

## Safety
- Migration is idempotent (`IF NOT EXISTS`, `CREATE OR REPLACE`, trigger drop/recreate).
- Safe to run multiple times.
- Non-Postgres environments are skipped by guard.
