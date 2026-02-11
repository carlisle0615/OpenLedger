from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str | None = None) -> str | None:
    """
    将空字符串视为“未设置”，避免用户 export 了变量但忘记赋值时出现意外行为。
    """
    v = os.environ.get(key)
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


def load_settings() -> Settings:
    host = _env("OPENLEDGER_HOST", "127.0.0.1") or "127.0.0.1"
    port = _parse_int(_env("OPENLEDGER_PORT", "8000"), 8000)

    open_browser = _parse_bool(_env("OPENLEDGER_OPEN_BROWSER", None), True)

    log_level = (_env("OPENLEDGER_LOG_LEVEL", "INFO") or "INFO").upper()

    max_upload_mb = _parse_int(_env("OPENLEDGER_MAX_UPLOAD_MB", "50"), 50)
    if max_upload_mb <= 0:
        # "0" 很容易踩坑；这里保持一个保守默认值。
        max_upload_mb = 50
    max_upload_bytes = max_upload_mb * 1024 * 1024

    return Settings(
        host=host,
        port=port,
        open_browser=open_browser,
        log_level=log_level,
        max_upload_bytes=max_upload_bytes,
    )
