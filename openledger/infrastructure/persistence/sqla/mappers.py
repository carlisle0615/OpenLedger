from __future__ import annotations

from typing import Any

from sqlalchemy.engine import Row


def row_to_dict(row: Row[Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row._mapping)
