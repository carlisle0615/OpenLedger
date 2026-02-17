from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Profile:
    id: str
    name: str
    created_at: str
    updated_at: str
    bills: list[dict[str, Any]] = field(default_factory=list)
