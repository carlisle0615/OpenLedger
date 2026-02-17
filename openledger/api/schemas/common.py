from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ApiErrorModel(ResponseModel):
    code: str
    message: str
    details: Any | None = None


def ok(payload: Any, *, request_id: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    envelope_meta = {"request_id": request_id}
    if meta:
        envelope_meta.update(meta)
    return {"data": payload, "meta": envelope_meta}


def err(
    *,
    request_id: str,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "request_id": request_id,
    }
