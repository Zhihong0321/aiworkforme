import sqlite3
import os

db_path = "app_test.db"
if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables: {tables}")
        
        cursor.execute("SELECT * FROM zairag_agents;")
        agents = cursor.fetchall()
        print(f"Agents in zairag_agents: {agents}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
