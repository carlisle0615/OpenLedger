from __future__ import annotations

from pydantic import Field

from openledger.api.schemas.common import RequestModel


class CreateProfilePayload(RequestModel):
    name: str = Field(min_length=1, max_length=80)


class AddBillPayload(RequestModel):
    run_id: str = Field(min_length=1)
    period_year: int | None = Field(default=None, ge=1900, le=2200)
    period_month: int | None = Field(default=None, ge=1, le=12)


class RemoveBillsPayload(RequestModel):
    period_key: str | None = None
    run_id: str | None = None


class ReimportBillPayload(RequestModel):
    period_key: str = Field(min_length=1)
    run_id: str = Field(min_length=1)


class UpdateProfilePayload(RequestModel):
    name: str | None = Field(default=None, max_length=80)
