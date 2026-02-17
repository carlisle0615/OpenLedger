from __future__ import annotations

from sqlalchemy.engine import Connection

from .models import metadata


def ensure_profiles_schema(conn: Connection) -> None:
    metadata.create_all(bind=conn, checkfirst=True)
