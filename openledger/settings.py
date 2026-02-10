from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str | None = None, *, legacy: tuple[str, ...] = ()) -> str | None:
    """
    Read an env var with optional legacy fallbacks.

    We treat empty strings as "unset" to avoid surprising behavior when users
    export variables but forget to assign values.
    """
    for k in (key, *legacy):
        v = os.environ.get(k)
        if v is not None and str(v).strip() != "":
            return v
    return default


def _parse_bool(v: str | None, default: bool) -> bool:
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _parse_int(v: str | None, default: int) -> int:
    if v is None:
        return default
    try:
        return int(str(v).strip())
    except Exception:
        return default


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    open_browser: bool
    log_level: str
    max_upload_bytes: int
    api_token: str | None


def load_settings() -> Settings:
    host = _env("OPENLEDGER_HOST", "127.0.0.1", legacy=("AUTO_ACCOUNTING_HOST",)) or "127.0.0.1"
    port = _parse_int(_env("OPENLEDGER_PORT", "8000", legacy=("AUTO_ACCOUNTING_PORT",)), 8000)

    open_browser = _parse_bool(_env("OPENLEDGER_OPEN_BROWSER", None), True)

    log_level = (_env("OPENLEDGER_LOG_LEVEL", "INFO", legacy=("AUTO_ACCOUNTING_LOG_LEVEL",)) or "INFO").upper()

    max_upload_mb = _parse_int(_env("OPENLEDGER_MAX_UPLOAD_MB", "50"), 50)
    if max_upload_mb <= 0:
        # "0" is a foot-gun; keep a conservative default.
        max_upload_mb = 50
    max_upload_bytes = max_upload_mb * 1024 * 1024

    api_token = _env("OPENLEDGER_API_TOKEN", None)

    return Settings(
        host=host,
        port=port,
        open_browser=open_browser,
        log_level=log_level,
        max_upload_bytes=max_upload_bytes,
        api_token=api_token,
    )
