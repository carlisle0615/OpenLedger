from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Bill:
    run_id: str
    period_key: str
    year: int | None
    month: int | None
