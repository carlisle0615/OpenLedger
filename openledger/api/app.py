from __future__ import annotations

import threading
import webbrowser
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

from openledger.api.dependencies import build_context
from openledger.api.error_handlers import register_error_handlers
from openledger.api.routers.capabilities import router as capabilities_router
from openledger.api.routers.config import router as config_router
from openledger.api.routers.health import router as health_router
from openledger.api.routers.preview import router as preview_router
from openledger.api.routers.profiles import router as profiles_router
from openledger.api.routers.runs import router as runs_router
from openledger.observability.logging import get_logger, setup_logging
from openledger.observability.request_context import (
    current_request_id,
    reset_request_id,
    set_request_id,
)
from openledger.settings import Settings, load_settings


def create_app(root: Path) -> FastAPI:
    settings = load_settings()
    setup_logging(settings)

    app = FastAPI(title="OpenLedger API", version="2.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.ctx = build_context(root)

    logger = get_logger()

    def _extract_log_scope(path: str) -> tuple[str, str]:
        parts = [seg for seg in path.split("/") if seg]
        run_id = "-"
        stage_id = "-"
        # /api/v2/runs/{run_id}
        if len(parts) >= 4 and parts[0] == "api" and parts[1] == "v2" and parts[2] == "runs":
            run_id = parts[3] or "-"
        # /api/v2/runs/{run_id}/stages/{stage_id}/...
        if (
            len(parts) >= 6
            and parts[0] == "api"
            and parts[1] == "v2"
            and parts[2] == "runs"
            and parts[4] == "stages"
        ):
            stage_id = parts[5] or "-"
        return run_id, stage_id

    def _request_logger(request: Request, request_id: str):
        run_id, stage_id = _extract_log_scope(request.url.path)
        return logger.bind(
            request_id=request_id,
            run_id=run_id,
            stage_id=stage_id,
            method=request.method,
            path=request.url.path,
        )

    @app.middleware("http")
    async def request_log_middleware(request: Request, call_next):
        request_id = (
            str(request.headers.get("x-request-id", "") or "").strip()
            or uuid4().hex[:16]
        )
        token = set_request_id(request_id)
        started = perf_counter()
        req_logger = _request_logger(request, request_id)
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (perf_counter() - started) * 1000
            req_logger.bind(status_code=500).opt(exception=True).error(
                f"request failed duration_ms={duration_ms:.2f}"
            )
            reset_request_id(token)
            raise

        duration_ms = (perf_counter() - started) * 1000
        response.headers["X-Request-Id"] = request_id
        status_code = int(response.status_code)
        message = f"request completed status={status_code} duration_ms={duration_ms:.2f}"
        if status_code >= 500:
            req_logger.bind(status_code=status_code).error(message)
        elif status_code >= 400:
            req_logger.bind(status_code=status_code).warning(message)
        else:
            req_logger.bind(status_code=status_code).info(message)
        reset_request_id(token)
        return response

    register_error_handlers(app)

    prefix = "/api/v2"
    app.include_router(health_router, prefix=prefix)
    app.include_router(capabilities_router, prefix=prefix)
    app.include_router(config_router, prefix=prefix)
    app.include_router(runs_router, prefix=prefix)
    app.include_router(preview_router, prefix=prefix)
    app.include_router(profiles_router, prefix=prefix)

    @app.api_route("/api/v2/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    async def api_v2_not_found(rest: str) -> Response:
        raise HTTPException(status_code=404, detail=f"route not found: /api/v2/{rest}")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def fallback(full_path: str) -> Response:
        if full_path.startswith("api/"):
            return HTMLResponse(
                "<html><body><h3>Not Found</h3><p>Use /api/v2/* endpoints.</p></body></html>",
                status_code=404,
            )
        return HTMLResponse(
            "<html><body>"
            "<h3>OpenLedger server is running.</h3>"
            "<p>Frontend is not served by this backend. Run <code>pnpm install</code> and <code>pnpm dev</code> under <code>web/</code>.</p>"
            "</body></html>"
        )

    return app


def serve(
    root: Path, host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True
) -> None:
    settings: Settings = load_settings()
    setup_logging(settings)
    app = create_app(root)
    url = f"http://{host}:{port}"
    logger = get_logger()
    logger.bind(run_id="-", stage_id="-").info(f"UI 服务地址 -> {url}")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=settings.log_level.lower(),
        log_config=None,
    )


def main() -> None:
    root = Path.cwd()
    settings = load_settings()
    serve(
        root=root,
        host=settings.host,
        port=settings.port,
        open_browser=settings.open_browser,
    )
