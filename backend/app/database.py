"""SQLAlchemy engine, session factory, and shared model helpers."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Naive UTC timestamp (DateTime columns are timezone-naive)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


_connect_args = {"check_same_thread": False} if settings.uses_sqlite else {}

engine = create_engine(settings.database_url, connect_args=_connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
