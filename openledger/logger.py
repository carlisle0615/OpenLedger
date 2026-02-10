from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable

from .settings import load_settings

@dataclass(frozen=True)
class _FallbackLogger:
    _emit: Callable[[str], None]
    _extra: dict[str, Any]

    def bind(self, **extra: Any) -> "_FallbackLogger":
        merged = dict(self._extra)
        merged.update(extra)
        return _FallbackLogger(_emit=self._emit, _extra=merged)

    def _prefix(self) -> str:
        run_id = str(self._extra.get("run_id", "-"))
        stage_id = str(self._extra.get("stage_id", "-"))
        return f"[{run_id} {stage_id}]"

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


@lru_cache(maxsize=1)
def get_logger():
    level = load_settings().log_level
    try:
        from loguru import logger as _logger  # type: ignore
    except Exception:
        # Minimal fallback (still prints progress).
        return _FallbackLogger(_emit=lambda s: print(s, file=sys.stdout, flush=True), _extra={"run_id": "-", "stage_id": "-"})

    _logger.remove()
    _logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[run_id]}</cyan> <magenta>{extra[stage_id]}</magenta> | {message}",
    )
    return _logger.bind(run_id="-", stage_id="-")
