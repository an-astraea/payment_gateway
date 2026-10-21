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
    _add_missing_columns()
    with SessionLocal() as db:
        seed(db)


def _add_missing_columns() -> None:
    """Small built-in upgrade step: adds columns that newer versions of the models define
    to tables created by an older version, so existing data is kept. Use Alembic for
    anything more complex (renames, type changes) in production."""
    from sqlalchemy import Integer, inspect, text

    insp = inspect(engine)
    added = []
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        existing = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing:
                continue
            ddl = f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(dialect=engine.dialect)}"
            if isinstance(col.type, Integer) and not col.nullable:
                ddl += " DEFAULT 0"
            with engine.begin() as conn:
                conn.execute(text(ddl))
            added.append(f"{table.name}.{col.name}")
    if "bookings.base_fee_paise" in added:
        with engine.begin() as conn:
            conn.execute(text("UPDATE bookings SET base_fee_paise = fee_paise WHERE base_fee_paise = 0 OR base_fee_paise IS NULL"))
    if added:
        import logging

        logging.getLogger("booking").info("Database upgraded, added columns: %s", ", ".join(added))