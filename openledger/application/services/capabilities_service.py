from __future__ import annotations

from openledger.application.services.capabilities_core import (
    get_capabilities_payload,
    get_pdf_parser_health,
    list_source_support_matrix,
)
from openledger.parsers.pdf import list_pdf_modes


def list_pdf_modes_payload() -> dict:
    return {"modes": list_pdf_modes()}


def get_pdf_parser_health_payload() -> dict:
    return get_pdf_parser_health()


def get_source_support_payload() -> dict:
    return {"sources": list_source_support_matrix()}


def get_capabilities_payload_v2() -> dict:
    return get_capabilities_payload()
