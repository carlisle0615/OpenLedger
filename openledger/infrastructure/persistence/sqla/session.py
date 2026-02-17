from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy.engine import Connection, Engine


@contextmanager
def connection_scope(engine: Engine) -> Iterator[Connection]:
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        yield conn
