from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RunState:
    run_id: str
    status: str
    created_at: str
    updated_at: str
    cancel_requested: bool
    current_stage: str | None
    options: dict[str, Any] = field(default_factory=dict)
    inputs: list[dict[str, Any]] = field(default_factory=list)
    stages: list[dict[str, Any]] = field(default_factory=list)
