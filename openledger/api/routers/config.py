from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from openledger.api.dependencies import ApiContext, get_ctx
from openledger.api.schemas.common import ok
from openledger.api.schemas.config import JsonObjectPayload
from openledger.application.services.config_service import (
    get_global_classifier_config,
    get_run_classifier_config,
    update_global_classifier_config,
    update_run_classifier_config,
)
from openledger.observability.request_context import current_request_id

router = APIRouter(tags=["config"])


@router.get("/config/classifier")
async def get_global_classifier(ctx: Annotated[ApiContext, Depends(get_ctx)]) -> dict:
    try:
        payload = get_global_classifier_config(ctx.root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="config not found") from exc
    return ok(payload, request_id=current_request_id())


@router.put("/config/classifier")
async def put_global_classifier(
    payload: JsonObjectPayload,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    update_global_classifier_config(ctx.root, payload.root)
    return ok({"ok": True}, request_id=current_request_id())


@router.get("/runs/{run_id}/config/classifier")
async def get_run_classifier(
    run_id: str,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    try:
        payload = get_run_classifier_config(ctx.root, run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="config not found") from exc
    return ok(payload, request_id=current_request_id())


@router.put("/runs/{run_id}/config/classifier")
async def put_run_classifier(
    run_id: str,
    payload: JsonObjectPayload,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    update_run_classifier_config(ctx.root, run_id, payload.root)
    return ok({"ok": True}, request_id=current_request_id())
