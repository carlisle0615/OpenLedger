from __future__ import annotations

from enum import StrEnum


class RunStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    NEEDS_REVIEW = "needs_review"


class ClassifyMode(StrEnum):
    LLM = "llm"
    DRY_RUN = "dry_run"


class PeriodMode(StrEnum):
    BILLING = "billing"
    CALENDAR = "calendar"
