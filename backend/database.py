import os
from sqlmodel import create_engine, Session

# Get DATABASE_URL from env, default to local docker container
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:db_password" + "@db:5432/chatbot_db")

# Fix for some PaaS that return postgres:// which SQLAlchemy 1.4+ deprecated
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def get_session():
    with Session(engine) as session:
        yield session
