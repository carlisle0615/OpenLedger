from __future__ import annotations

import logging
import sys
from contextvars import ContextVar, Token
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, cast

from .settings import Settings, load_settings

_REQUEST_ID: ContextVar[str] = ContextVar("openledger_request_id", default="-")
_LOGGING_CONFIGURED = False


def current_request_id() -> str:
    request_id = str(_REQUEST_ID.get() or "").strip()
    return request_id or "-"


def set_request_id(request_id: str) -> Token[str]:
    value = str(request_id or "").strip() or "-"
    return _REQUEST_ID.set(value)


def reset_request_id(token: Token[str]) -> None:
    _REQUEST_ID.reset(token)


@dataclass(frozen=True)
class _FallbackLogger:
    _emit: Callable[[str], None]
    _extra: dict[str, str]

    def bind(self, **extra: str) -> "_FallbackLogger":
        merged = dict(self._extra)
        for key, value in extra.items():
            merged[key] = str(value)
        return _FallbackLogger(_emit=self._emit, _extra=merged)

    def _prefix(self) -> str:
        run_id = str(self._extra.get("run_id", "-"))
        stage_id = str(self._extra.get("stage_id", "-"))
        request_id = str(self._extra.get("request_id", current_request_id()))
        return f"[rid={request_id} run={run_id} stage={stage_id}]"

    def _log(self, level: str, message: str) -> None:
        self._emit(f"{level} {self._prefix()} {message}")

    def info(self, message: str) -> None:
        self._log("INFO ", message)

    def warning(self, message: str) -> None:
        self._log("WARN ", message)

    def error(self, message: str) -> None:
        self._log("ERROR", message)

    def debug(self, message: str) -> None:
        self._log("DEBUG", message)


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            from loguru import logger as loguru_logger  # type: ignore
        except Exception:
            return

        level_name = record.levelname
        try:
            target_level: str | int = loguru_logger.level(level_name).name
        except Exception:
            target_level = record.levelno

        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(target_level, record.getMessage())


def _patch_record(record: dict[str, object]) -> None:
    extra = cast(dict[str, object], record["extra"])
    run_id = str(extra.get("run_id", "-") or "-").strip() or "-"
    stage_id = str(extra.get("stage_id", "-") or "-").strip() or "-"
    request_id = str(extra.get("request_id", "") or "").strip() or current_request_id()
    extra["run_id"] = run_id
    extra["stage_id"] = stage_id
    extra["request_id"] = request_id


def setup_logging(settings: Settings | None = None) -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    config = settings or load_settings()

    try:
        from loguru import logger as loguru_logger  # type: ignore
    except Exception:
        _LOGGING_CONFIGURED = True
        return

    loguru_logger.remove()
    loguru_logger.configure(patcher=_patch_record)
    format_text = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "rid=<yellow>{extra[request_id]}</yellow> "
        "run=<cyan>{extra[run_id]}</cyan> "
        "stage=<magenta>{extra[stage_id]}</magenta> | "
        "{message}"
    )
    loguru_logger.add(
        sys.stdout,
        level=config.log_level,
        format=format_text,
        colorize=not config.log_json,
        serialize=config.log_json,
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )

    if config.log_path:
        path = Path(config.log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        loguru_logger.add(
            str(path),
            level=config.log_level,
            serialize=True,
            enqueue=True,
            backtrace=True,
            diagnose=False,
            rotation=f"{config.log_rotation_mb} MB",
            retention=f"{config.log_retention_days} days",
            compression="gz",
        )

    intercept = _InterceptHandler()
    root_logger = logging.getLogger()
    root_logger.handlers = [intercept]
    root_logger.setLevel(config.log_level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "starlette", "asyncio"):
        logger_obj = logging.getLogger(name)
        logger_obj.handlers = [intercept]
        logger_obj.propagate = False
        logger_obj.setLevel(config.log_level)

    _LOGGING_CONFIGURED = True


@lru_cache(maxsize=1)
def get_logger():
    setup_logging(load_settings())
    try:
        from loguru import logger as loguru_logger  # type: ignore
    except Exception:
        return _FallbackLogger(
            _emit=lambda s: print(s, file=sys.stdout, flush=True),
            _extra={"run_id": "-", "stage_id": "-", "request_id": "-"},
        )
    return loguru_logger.bind(run_id="-", stage_id="-", request_id="-")
