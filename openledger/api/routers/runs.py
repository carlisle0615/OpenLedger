from __future__ import annotations

import mimetypes
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from openledger.api.dependencies import ApiContext, get_ctx
from openledger.api.schemas.common import ok
from openledger.api.schemas.runs import (
    CreateRunPayload,
    ResetPayload,
    ReviewUpdatesPayload,
    RunOptionsPatch,
    SetProfileBindingPayload,
    StartRunPayload,
)
from openledger.application.services.profile_service import (
    clear_run_binding_payload,
    get_run_binding_payload,
    set_run_binding_payload,
)
from openledger.application.services.run_service import (
    create_run_state,
    get_match_stats,
    get_run_state,
    get_stage_io,
    list_run_artifacts,
    list_runs_payload,
    save_upload_files,
    update_run_options,
)
from openledger.observability.request_context import current_request_id
from openledger.state import resolve_under_root
from openledger.infrastructure.workflow.runtime import make_paths

router = APIRouter(tags=["runs"])


@router.get("/runs")
async def get_runs(ctx: Annotated[ApiContext, Depends(get_ctx)]) -> dict:
    return ok(list_runs_payload(ctx.root), request_id=current_request_id())


@router.post("/runs")
async def create_run(
    ctx: Annotated[ApiContext, Depends(get_ctx)],
    payload: CreateRunPayload | None = Body(default=None),
) -> dict:
    state = create_run_state(ctx.root, name=(payload.name if payload else ""))
    return ok(state, request_id=current_request_id())


@router.get("/runs/{run_id}")
async def get_run(run_id: str, ctx: Annotated[ApiContext, Depends(get_ctx)]) -> dict:
    return ok(get_run_state(ctx.root, run_id), request_id=current_request_id())


@router.get("/runs/{run_id}/artifacts")
async def get_artifacts(run_id: str, ctx: Annotated[ApiContext, Depends(get_ctx)]) -> dict:
    artifacts = list_run_artifacts(ctx.root, run_id)
    return ok({"artifacts": artifacts}, request_id=current_request_id())


@router.get("/runs/{run_id}/artifact")
async def download_artifact(
    run_id: str,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
    path: str = Query(min_length=1),
) -> FileResponse:
    paths = make_paths(ctx.root, run_id)
    file_path = resolve_under_root(paths.run_dir, path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    return FileResponse(file_path, media_type=mime_type, filename=file_path.name)


@router.get("/runs/{run_id}/stages/{stage_id}/io")
async def stage_io(
    run_id: str,
    stage_id: str,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    return ok(get_stage_io(ctx.root, run_id, stage_id), request_id=current_request_id())


@router.get("/runs/{run_id}/stats/match")
async def match_stats(
    run_id: str,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
    stage: Literal["match_credit_card", "match_bank"] = Query(...),
) -> dict:
    payload = get_match_stats(ctx.root, run_id, stage=stage)
    return ok(payload, request_id=current_request_id())


@router.post("/runs/{run_id}/files")
async def upload_files(
    run_id: str,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
    request: Request,
    files: list[UploadFile] = File(...),
) -> dict:
    content_length = request.headers.get("content-length", "")
    if not content_length:
        raise HTTPException(status_code=400, detail="missing Content-Length")
    total_bytes = int(content_length)
    max_bytes = ctx.settings.max_upload_bytes
    if total_bytes > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"payload too large: {total_bytes} > {max_bytes}",
        )
    try:
        saved = save_upload_files(ctx.root, run_id, files)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    return ok({"saved": saved}, request_id=current_request_id())


@router.post("/runs/{run_id}/commands/start")
async def start_run(
    run_id: str,
    payload: StartRunPayload,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    options_payload = payload.options.model_dump(exclude_unset=True)
    ctx.workflow.start(
        run_id,
        stages=payload.stages,
        options=cast(dict[str, object], options_payload),
    )
    return ok({"ok": True, "run_id": run_id}, request_id=current_request_id())


@router.post("/runs/{run_id}/commands/cancel")
async def cancel_run(
    run_id: str,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    ctx.workflow.cancel(run_id)
    return ok({"ok": True}, request_id=current_request_id())


@router.post("/runs/{run_id}/commands/reset")
async def reset_run(
    run_id: str,
    payload: ResetPayload,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    if payload.scope != "classify":
        raise HTTPException(status_code=400, detail=f"unknown scope: {payload.scope}")
    try:
        ctx.workflow.reset_classify(run_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok({"ok": True, "scope": payload.scope}, request_id=current_request_id())


@router.post("/runs/{run_id}/review/updates")
async def update_review(
    run_id: str,
    payload: ReviewUpdatesPayload,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    try:
        updated = ctx.workflow.apply_review_updates(
            run_id, [item.model_dump(exclude_unset=True) for item in payload.updates]
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="review.csv not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok({"ok": True, "updated": updated}, request_id=current_request_id())


@router.put("/runs/{run_id}/options")
async def put_options(
    run_id: str,
    payload: RunOptionsPatch,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    try:
        update_run_options(ctx.root, run_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok({"ok": True}, request_id=current_request_id())


@router.get("/runs/{run_id}/profile-binding")
async def get_profile_binding(
    run_id: str,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    try:
        binding = get_run_binding_payload(ctx.root, run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    return ok({"run_id": run_id, "binding": binding}, request_id=current_request_id())


@router.put("/runs/{run_id}/profile-binding")
async def put_profile_binding(
    run_id: str,
    payload: SetProfileBindingPayload,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    profile_id = payload.profile_id.strip()
    try:
        if profile_id:
            binding = set_run_binding_payload(ctx.root, run_id, profile_id)
        else:
            clear_run_binding_payload(ctx.root, run_id)
            binding = None
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run or profile not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok({"ok": True, "binding": binding}, request_id=current_request_id())
