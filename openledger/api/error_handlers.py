from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from openledger.api.schemas.common import err
from openledger.domain.errors import DomainError
from openledger.observability.request_context import current_request_id


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=err(
                request_id=current_request_id(),
                code=exc.code,
                message=exc.message,
                details=exc.details,
            ),
        )

    @app.exception_handler(HTTPException)
    async def _http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
        code = "http_error"
        if exc.status_code == 404:
            code = "not_found"
        elif exc.status_code == 409:
            code = "conflict"
        elif exc.status_code == 422:
            code = "validation_error"
        return JSONResponse(
            status_code=exc.status_code,
            content=err(
                request_id=current_request_id(),
                code=code,
                message=str(exc.detail),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=err(
                request_id=current_request_id(),
                code="validation_error",
                message="request validation failed",
                details=exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def _generic_error_handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=err(
                request_id=current_request_id(),
                code="internal_error",
                message="internal server error",
            ),
        )
