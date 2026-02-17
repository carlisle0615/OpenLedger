from __future__ import annotations

from fastapi import APIRouter

from openledger.api.schemas.common import ok
from openledger.application.services.capabilities_service import (
    get_capabilities_payload_v2,
    get_pdf_parser_health_payload,
    get_source_support_payload,
    list_pdf_modes_payload,
)
from openledger.observability.request_context import current_request_id

router = APIRouter(tags=["capabilities"])


@router.get("/parsers/pdf")
async def parsers_pdf() -> dict:
    return ok(list_pdf_modes_payload(), request_id=current_request_id())


@router.get("/parsers/pdf/health")
async def parsers_pdf_health() -> dict:
    return ok(get_pdf_parser_health_payload(), request_id=current_request_id())


@router.get("/sources/support")
async def source_support() -> dict:
    return ok(get_source_support_payload(), request_id=current_request_id())


@router.get("/capabilities")
async def capabilities() -> dict:
    return ok(get_capabilities_payload_v2(), request_id=current_request_id())
