from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_bootstrapped = False


def is_postgresql_url(database_url: str) -> bool:
    return database_url.startswith("postgresql")


def _build_engine(database_url: str) -> Engine:
    engine_kwargs: dict[str, object] = {"future": True}
    settings = get_settings()
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        if database_url in {"sqlite://", "sqlite:///:memory:"}:
            engine_kwargs["poolclass"] = StaticPool
    elif is_postgresql_url(database_url) and settings.database_schema:
        engine_kwargs["connect_args"] = {"options": f"-csearch_path={settings.database_schema}"}
    return create_engine(database_url, **engine_kwargs)


def ensure_database_schema(engine: Engine) -> None:
    settings = get_settings()
    if not is_postgresql_url(settings.database_url):
        return

    schema_name = settings.database_schema.strip()
    if not schema_name or schema_name == "public":
        return

    quoted_schema = schema_name.replace('"', '""')
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{quoted_schema}"'))


def init_engine(force: bool = False) -> Engine:
    global _engine, _session_factory

    if _engine is not None and not force:
        return _engine

    if _engine is not None and force:
        _engine.dispose()

    settings = get_settings()
    _engine = _build_engine(settings.database_url)
    _session_factory = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return _engine


def bootstrap_database(force: bool = False) -> Engine:
    global _bootstrapped

    if _bootstrapped and not force:
        return get_engine()

    engine = init_engine(force=force)

    from app.models import Base
    from app.services.seed import seed_demo_data

    settings = get_settings()
    ensure_database_schema(engine)

    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)

    if settings.seed_demo_data and settings.app_env != "production" and inspect(engine).has_table("merchants"):
        session_local = get_session_factory()
        db = session_local()
        try:
            seed_demo_data(db)
        finally:
            db.close()

    _bootstrapped = True
    return engine


def get_engine() -> Engine:
    if _engine is None:
        return init_engine()
    return _engine


def reset_engine() -> None:
    global _engine, _session_factory, _bootstrapped

    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
    _bootstrapped = False


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        init_engine()
    assert _session_factory is not None
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    if not _bootstrapped:
        bootstrap_database()

    session_local = get_session_factory()
    db = session_local()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    if not _bootstrapped:
        bootstrap_database()

    session_local = get_session_factory()
    db = session_local()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
