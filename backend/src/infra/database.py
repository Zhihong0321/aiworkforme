"""
MODULE: Infrastructure - Database
PURPOSE: Shared SQLAlchemy engine and session management.
"""
import os
from sqlmodel import Session, create_engine

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("POSTGRES_URL")
    or os.getenv("POSTGRESQL_URL")
    or "postgresql://user:password@db:5432/chatbot_db"
)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=False)

def get_session():
    with Session(engine) as session:
        yield session
