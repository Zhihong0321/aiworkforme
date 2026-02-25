"""
Migration: Add optional behaviour columns to zairag_agents
  - mimic_human_typing  BOOLEAN  DEFAULT FALSE
  - emoji_level         VARCHAR  DEFAULT 'none'   ('none'/'low'/'high')
  - segment_delay_ms    INTEGER  DEFAULT 800       (ms delay between message segments)
"""
import psycopg2

DB_URL = "postgres://postgres:qsLdbwueuhAJKIsVvhn06~77IvUMNbAz@turntable.proxy.rlwy.net:23554/railway"

DDL = [
    "ALTER TABLE zairag_agents ADD COLUMN IF NOT EXISTS mimic_human_typing BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE zairag_agents ADD COLUMN IF NOT EXISTS emoji_level VARCHAR(10) NOT NULL DEFAULT 'none'",
    "ALTER TABLE zairag_agents ADD COLUMN IF NOT EXISTS segment_delay_ms INTEGER NOT NULL DEFAULT 800",
]

def main():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    for stmt in DDL:
        print(f"Executing: {stmt}")
        cur.execute(stmt)
        print("  OK")

    cur.execute(
        "SELECT column_name, data_type, column_default "
        "FROM information_schema.columns "
        "WHERE table_name = 'zairag_agents' ORDER BY ordinal_position"
    )
    print("\nzairag_agents columns after migration:")
    for row in cur.fetchall():
        print(" ", row)

    cur.close()
    conn.close()
    print("\nMigration complete.")

if __name__ == "__main__":
    main()
