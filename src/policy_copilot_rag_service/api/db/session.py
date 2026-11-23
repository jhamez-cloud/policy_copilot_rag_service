'''Creating and Initializing DB engine and session management'''
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session,sessionmaker
from ...settings import get_settings
from .migrations import upgrade_schema
from .models import Base
from .repository import ensure_system_library
from collections.abc import Iterator

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def _configure_sqlite(engine: Engine) -> None:
    if engine.dialect.name == "sqlite" and not event.contains(
        engine, "connect", _sqlite_foreign_keys
    ):
        event.listen(engine, "connect", _sqlite_foreign_keys)


def get_engine() -> Engine:
    global _engine

    if _engine is None:
        url = get_settings().neon_database_url
        if url.startswith("sqlite"):
            _engine = create_engine(url,connect_args={"check_same_thread":False})
        else:
            _engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=5,
                max_overflow=5
            )

        _configure_sqlite(_engine)

    return _engine


def init_db() -> None:
    """Create missing tables and safely upgrade an existing document schema."""
    engine = get_engine()
    _configure_sqlite(engine)
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            # Multiple app instances may start against the same Neon database.
            # Serialize schema setup until this transaction commits or rolls back.
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(7289057126754832)")
        elif engine.dialect.name == "sqlite":
            # Also enable connections already pooled before the connect listener.
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(connection)
        upgrade_schema(connection)
        # This runs even when directory seeding is disabled or unavailable.
        # The surrounding transaction/lock also covers singleton creation and
        # backfilling policies already present in an older database.
        with Session(bind=connection, expire_on_commit=False) as db:
            ensure_system_library(db)


def get_session_factory():
    global _session_factory

    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(),expire_on_commit=False)

    return _session_factory


def get_db() -> Iterator[Session]:
    db = get_session_factory()()

    try:
        yield db
    finally:
        db.close()


def dispose_engine() -> None:
    global _engine,_session_factory

    if _engine is not None:
        _engine.dispose()

    _engine = None
    _session_factory = None
