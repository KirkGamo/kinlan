"""Database engine, session factory and the declarative base for every model."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

# Stable constraint names, so Alembic migrations stay reviewable and reversible.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all KinLAN tables."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


@lru_cache
def get_engine() -> Engine:
    """One engine per process. pre_ping replaces connections Neon dropped while idle."""
    engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5)

    @event.listens_for(engine, "connect")
    def _utc(dbapi_connection, _record) -> None:
        # The API speaks UTC (ISO 8601); don't inherit the server's local zone (e.g. Asia/Manila).
        with dbapi_connection.cursor() as cur:
            cur.execute("SET TIME ZONE 'UTC'")
        dbapi_connection.commit()

    return engine


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
