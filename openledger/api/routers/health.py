from __future__ import annotations

from fastapi import APIRouter, Request

from openledger.api.schemas.common import ok
from openledger.observability.request_context import current_request_id

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(_: Request) -> dict:
    return ok({"ok": True}, request_id=current_request_id())
