import psycopg2

conn = psycopg2.connect("postgres://postgres:qsLdbwueuhAJKIsVvhn06~77IvUMNbAz@turntable.proxy.rlwy.net:23554/railway")
cur = conn.cursor()

# 1. Check zairag_system_settings - the REAL settings table
print("=== zairag_system_settings ===")
cur.execute("SELECT key, length(value) as val_len, left(value, 6) as prefix FROM zairag_system_settings")
rows = cur.fetchall()
if rows:
    for row in rows:
        print(f"  key={row[0]!r}, value_len={row[1]}, prefix={row[2]!r}")
else:
    print("  EMPTY - no settings at all!")

# 2. Check context_builder - what does build_context need?
# Check if et_strategy_versions has data for workspace 1
print()
print("=== et_strategy_versions for workspace 1 ===")
cur.execute("SELECT id, workspace_id, status, tone FROM et_strategy_versions WHERE workspace_id = 1")
rows = cur.fetchall()
print(rows if rows else "  NONE")

# 3. Check et_lead_memories for lead 3
print()
print("=== et_lead_memories for lead 3 ===")
cur.execute("SELECT id, lead_id, summary FROM et_lead_memories WHERE lead_id = 3")
rows = cur.fetchall()
print(rows if rows else "  NONE")

# 4. Check zairag_agent_knowledge_files for agent 1
print()
print("=== zairag_agent_knowledge_files for agent 1 ===")
cur.execute("SELECT id, agent_id, filename FROM zairag_agent_knowledge_files WHERE agent_id = 1")
rows = cur.fetchall()
print(rows if rows else "  NONE")

# 5. Check zairag_agents columns - does it still have model/reasoning_enabled?
print()
print("=== zairag_agents columns ===")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'zairag_agents' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(f"  {row[0]}")

# 6. Check agent 1 data
print()
print("=== Agent 1 data ===")
cur.execute("SELECT * FROM zairag_agents WHERE id = 1")
cols = [desc[0] for desc in cur.description]
row = cur.fetchone()
if row:
    for k, v in zip(cols, row):
        print(f"  {k}: {str(v)[:100]!r}")

conn.close()
print("\nDone.")
