from __future__ import annotations

import atexit
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_ENGINE_CACHE: dict[str, Engine] = {}


def build_db_url(db_path: Path) -> str:
    return f"sqlite+pysqlite:///{db_path}"


def get_engine(db_path: Path) -> Engine:
    key = str(db_path.resolve())
    engine = _ENGINE_CACHE.get(key)
    if engine is not None:
        return engine

    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        build_db_url(db_path),
        future=True,
        connect_args={"check_same_thread": False},
    )
    _ENGINE_CACHE[key] = engine
    return engine


def dispose_engine(db_path: Path) -> None:
    key = str(db_path.resolve())
    engine = _ENGINE_CACHE.pop(key, None)
    if engine is not None:
        engine.dispose()


def dispose_all_engines() -> None:
    for key, engine in list(_ENGINE_CACHE.items()):
        engine.dispose()
        _ENGINE_CACHE.pop(key, None)


atexit.register(dispose_all_engines)
