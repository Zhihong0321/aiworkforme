from pathlib import Path


def test_et_assign_inbound_thread_sets_required_timestamps():
    sql_path = Path(__file__).resolve().parents[1] / "sql" / "messaging_m1_unified_schema.sql"
    sql = sql_path.read_text(encoding="utf-8")

    assert "INSERT INTO et_threads (tenant_id, lead_id, channel, status, created_at, updated_at)" in sql
    assert "VALUES (NEW.tenant_id, NEW.lead_id, NEW.channel, 'active', NOW(), NOW())" in sql
