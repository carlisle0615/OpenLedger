from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Stage:
    id: str
    name: str
    status: str
