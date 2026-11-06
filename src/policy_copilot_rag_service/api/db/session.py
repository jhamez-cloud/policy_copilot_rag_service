'''Creating and Initializing DB engine and session management'''
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session,sessionmaker
from ...settings import get_settings
from .models import Base
from collections.abc import Iterator

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None

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

    return _engine


def init_db():
    '''Create tables for all DB Models (e.g. Document model), if they dont exist yet'''
    Base.metadata.create_all(get_engine())


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
