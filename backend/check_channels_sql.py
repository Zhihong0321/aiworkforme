import os
from sqlalchemy import create_engine, text

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("No DATABASE_URL found")
    exit(1)

engine = create_engine(db_url)
with engine.connect() as conn:
    result = conn.execute(text("SELECT id, channel_type, status FROM et_channel_sessions"))
    rows = result.fetchall()
    print(f"Found {len(rows)} channels:")
    for row in rows:
        print(dict(row._mapping))
