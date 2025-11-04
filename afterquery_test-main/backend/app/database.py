from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
import os

load_dotenv()

def _resolve_database_url() -> str:
    # Prefer explicit Supabase DB URL if provided, else fallback to DATABASE_URL, else local default
    url = os.getenv("SUPABASE_DB_URL")
    # Ensure sslmode=require for Supabase
    if "supabase.co" in url and "sslmode=" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"
    return url


DATABASE_URL = _resolve_database_url()

# Engine and session factory
# Supabase pooler in session mode has a very low max client limit.
# Keep our SQLAlchemy pool tiny to avoid exhausting the pooler.
create_engine_kwargs = dict(pool_pre_ping=True)
if "pooler.supabase.com" in DATABASE_URL or "supabase.co" in DATABASE_URL:
    create_engine_kwargs.update(dict(pool_size=1, max_overflow=0, pool_recycle=300, pool_use_lifo=True))

engine = create_engine(DATABASE_URL, **create_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
