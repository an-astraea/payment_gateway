"""Database entry point.

Everything that touches the database goes through this file. To switch databases, change
DATABASE_URL in .env (and install the driver). No other code needs to change.
For production schema changes, add Alembic migrations on top of this module.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables and seed the starting services and data."""
    from . import models  # noqa: F401  (registers the tables)
    from .seed import seed

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
