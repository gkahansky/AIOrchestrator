"""
Database engine and session factory.

Usage (in scripts / pipelines):
    from aiplatform.database.session import get_session

    with get_session() as db:
        db.add(job)
        db.commit()

Usage (in FastAPI — inject via Depends):
    from aiplatform.database.session import get_db

    def my_route(db: Session = Depends(get_db)):
        ...

The DATABASE_URL environment variable controls the connection:
  - Production/staging: set by Railway PostgreSQL plugin
      postgresql://user:pass@host:5432/dbname
  - Local development:
      postgresql://postgres:dev@localhost:5432/aiinfra
      or set DATABASE_URL in .ENV
  - Tests / CI (SQLite fallback):
      sqlite:///./test.db  (set DATABASE_URL=sqlite:///./test.db)
"""

import os
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent.parent / ".ENV")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:dev@localhost:5432/aiinfra",
)

# Railway provides postgres:// but SQLAlchemy 2.x requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs connect_args for thread safety in tests
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,       # reconnect on stale connections (important for Railway)
    pool_size=5,
    max_overflow=10,
    echo=False,               # set True locally to log all SQL
    # Do not connect on import — only when first query is made
    pool_recycle=300,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_session() -> Session:
    """Context manager for use in scripts and pipeline code."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """FastAPI dependency — yields a session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ping() -> bool:
    """Return True if the database is reachable. Used by health check endpoint."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
