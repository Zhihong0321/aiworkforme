import sqlite3
import os

db_path = "app_test.db"
if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(zairag_agents);")
        info = cursor.fetchall()
        for col in info:
            print(col)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
