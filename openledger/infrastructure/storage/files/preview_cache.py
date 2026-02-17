from __future__ import annotations

import hashlib
from pathlib import Path


def pdf_preview_cache_path(
    run_dir: Path,
    rel_path: str,
    *,
    mtime: float,
    page: int,
    dpi: int,
) -> Path:
    key = f"{rel_path}|{mtime:.3f}|{page}|{dpi}".encode("utf-8")
    digest = hashlib.sha1(key).hexdigest()[:16]
    cache_dir = run_dir / "preview"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"pdf_{digest}_p{page}_d{dpi}.png"
