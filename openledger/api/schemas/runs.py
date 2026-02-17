from __future__ import annotations

from typing import Literal

from pydantic import Field

from openledger.api.schemas.common import RequestModel
from openledger.domain.enums import ClassifyMode, PeriodMode


class CreateRunPayload(RequestModel):
    name: str = Field(default="", max_length=80)


class RunOptionsPatch(RequestModel):
    pdf_mode: str | None = None
    classify_mode: ClassifyMode | None = None
    period_mode: PeriodMode | None = None
    period_day: int | None = Field(default=None, ge=1, le=31)
    period_year: int | None = Field(default=None, ge=1900, le=2200)
    period_month: int | None = Field(default=None, ge=1, le=12)


class StartRunPayload(RequestModel):
    stages: list[str] | None = None
    options: RunOptionsPatch = Field(default_factory=RunOptionsPatch)


class ResetPayload(RequestModel):
    scope: Literal["classify"]


class ReviewUpdateItem(RequestModel):
    txn_id: str = Field(min_length=1)
    final_category_id: str | None = None
    final_note: str | None = None
    final_ignored: bool | None = None
    final_ignore_reason: str | None = None


class ReviewUpdatesPayload(RequestModel):
    updates: list[ReviewUpdateItem]


class SetProfileBindingPayload(RequestModel):
    profile_id: str = Field(min_length=1)
