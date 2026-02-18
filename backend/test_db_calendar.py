import sqlite3
import os

db_path = 'e:/AIworkforMe/backend/flow_test.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("--- MCP Servers ---")
cur.execute("SELECT name, script, status FROM zairag_mcp_servers")
for row in cur.fetchall():
    print(row)

print("\n--- Calendar Config ---")
try:
    cur.execute("SELECT * FROM et_calendar_configs")
    for row in cur.fetchall():
        print(row)
except sqlite3.OperationalError as e:
    print(f"Calendar Config table error: {e}")

print("\n--- Calendar Events ---")
try:
    cur.execute("SELECT * FROM et_calendar_events")
    for row in cur.fetchall():
        print(row)
except sqlite3.OperationalError as e:
    print(f"Calendar Events table error: {e}")

conn.close()
