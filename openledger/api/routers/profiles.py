from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from openledger.api.dependencies import ApiContext, get_ctx
from openledger.api.schemas.common import ok
from openledger.api.schemas.profiles import (
    AddBillPayload,
    CreateProfilePayload,
    ReimportBillPayload,
    RemoveBillsPayload,
    UpdateProfilePayload,
)
from openledger.application.services.profile_service import (
    add_bill_payload,
    check_profile_payload,
    create_profile_payload,
    get_profile_payload,
    list_profiles_payload,
    reimport_bill_payload,
    remove_bill_payload,
    update_profile_payload,
)
from openledger.application.services.review_service import build_profile_review_payload
from openledger.observability.request_context import current_request_id

router = APIRouter(tags=["profiles"])


@router.get("/profiles")
async def get_profiles(ctx: Annotated[ApiContext, Depends(get_ctx)]) -> dict:
    return ok(list_profiles_payload(ctx.root), request_id=current_request_id())


@router.post("/profiles")
async def create_profile(
    payload: CreateProfilePayload,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    profile = create_profile_payload(ctx.root, name=payload.name)
    return ok(profile, request_id=current_request_id())


@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: str, ctx: Annotated[ApiContext, Depends(get_ctx)]) -> dict:
    try:
        profile = get_profile_payload(ctx.root, profile_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="profile not found") from exc
    return ok(profile, request_id=current_request_id())


@router.put("/profiles/{profile_id}")
async def update_profile(
    profile_id: str,
    payload: UpdateProfilePayload,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    try:
        profile = update_profile_payload(
            ctx.root, profile_id, payload.model_dump(exclude_unset=True)
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="profile not found") from exc
    return ok(profile, request_id=current_request_id())


@router.get("/profiles/{profile_id}/check")
async def check_profile(
    profile_id: str, ctx: Annotated[ApiContext, Depends(get_ctx)]
) -> dict:
    try:
        payload = check_profile_payload(ctx.root, profile_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="profile not found") from exc
    return ok(payload, request_id=current_request_id())


@router.get("/profiles/{profile_id}/review")
async def profile_review(
    profile_id: str,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
    year: int | None = Query(default=None, ge=1900, le=2200),
    months: int = Query(default=12, ge=6, le=120),
) -> dict:
    try:
        payload = build_profile_review_payload(
            ctx.root, profile_id, year=year, months=months
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="profile not found") from exc
    return ok(payload, request_id=current_request_id())


@router.post("/profiles/{profile_id}/bills")
async def add_bill(
    profile_id: str,
    payload: AddBillPayload,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    try:
        profile = add_bill_payload(
            ctx.root,
            profile_id,
            run_id=payload.run_id,
            period_year=payload.period_year,
            period_month=payload.period_month,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="profile or run not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(profile, request_id=current_request_id())


@router.post("/profiles/{profile_id}/bills/remove")
async def remove_bill(
    profile_id: str,
    payload: RemoveBillsPayload,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    try:
        profile = remove_bill_payload(
            ctx.root,
            profile_id,
            period_key=payload.period_key,
            run_id=payload.run_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="profile not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(profile, request_id=current_request_id())


@router.post("/profiles/{profile_id}/bills/reimport")
async def reimport_bill(
    profile_id: str,
    payload: ReimportBillPayload,
    ctx: Annotated[ApiContext, Depends(get_ctx)],
) -> dict:
    try:
        profile = reimport_bill_payload(
            ctx.root,
            profile_id,
            period_key=payload.period_key,
            run_id=payload.run_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(profile, request_id=current_request_id())
