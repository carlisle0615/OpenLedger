from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MatchReason:
    reason: str
    count: int


@dataclass(slots=True)
class MatchStats:
    stage_id: str
    matched: int
    unmatched: int
    total: int
    match_rate: float
    unmatched_reasons: list[MatchReason]
