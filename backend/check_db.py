import psycopg2

conn = psycopg2.connect("postgres://postgres:qsLdbwueuhAJKIsVvhn06~77IvUMNbAz@turntable.proxy.rlwy.net:23554/railway")
cur = conn.cursor()

# Tables the agent runtime needs
tables_needed = [
    "et_policy_decisions",
    "et_strategy_versions",
    "et_lead_memories",
    "zairag_agent_knowledge_files",
    "et_conversation_threads",
    "et_chat_messages_new",
]
print("=== TABLE EXISTENCE CHECK ===")
for t in tables_needed:
    cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)", (t,))
    exists = cur.fetchone()[0]
    print(f"  {t}: {'EXISTS' if exists else 'MISSING <<<'}")

# Also check workspace table name
print()
print("=== WORKSPACE TABLE NAME ===")
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%workspace%'")
for row in cur.fetchall():
    print(" ", row[0])

# Check et_workspaces columns (does it have agent_id?)
print()
print("=== et_workspaces columns ===")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'et_workspaces'")
for row in cur.fetchall():
    print(" ", row[0])

conn.close()
print("Done.")
