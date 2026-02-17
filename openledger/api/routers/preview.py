from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from openledger.api.dependencies import ApiContext, get_ctx
from openledger.api.schemas.common import ok
from openledger.application.services.preview_service import (
    get_pdf_meta,
    preview_table,
    read_stage_log,
    render_pdf_page,
)
from openledger.observability.request_context import current_request_id

router = APIRouter(tags=["preview"])


@router.get("/runs/{run_id}/preview/table")
async def get_preview_table(
    run_id: str,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
    path: str = Query(min_length=1),
    limit: int = Query(default=50, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    try:
        payload = preview_table(ctx.root, run_id, path, limit=limit, offset=offset)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(payload, request_id=current_request_id())


@router.get("/runs/{run_id}/preview/pdf/meta")
async def get_preview_pdf_meta(
    run_id: str,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
    path: str = Query(min_length=1),
) -> dict:
    try:
        payload = get_pdf_meta(ctx.root, run_id, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(payload, request_id=current_request_id())


@router.get("/runs/{run_id}/preview/pdf/page")
async def get_preview_pdf_page(
    run_id: str,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
    path: str = Query(min_length=1),
    page: int = Query(default=1, ge=1),
    dpi: int = Query(default=120, ge=72, le=200),
) -> Response:
    try:
        data = render_pdf_page(ctx.root, run_id, path, page=page, dpi=dpi)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(content=data, media_type="image/png")


@router.get("/runs/{run_id}/stages/{stage_id}/log")
async def get_stage_log(
    run_id: str,
    stage_id: str,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    try:
        text = read_stage_log(ctx.root, run_id, stage_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="log not found") from exc
    return ok({"text": text}, request_id=current_request_id())
