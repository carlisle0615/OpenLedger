from __future__ import annotations

import re
from pathlib import Path


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\u4e00-\u9fff-]+")


def safe_filename(raw: str, *, default: str = "upload.bin", max_len: int = 180) -> str:
    """
    Convert a user-provided filename (e.g. multipart upload) into a safe basename.

    - Strips any directory components.
    - Removes control chars and path separators.
    - Collapses unsafe chars to underscores.
    - Prevents dot-only names like '.' and '..'.
    """
    name = str(raw or "").strip().replace("\x00", "")
    name = Path(name).name  # drop any path components
    name = name.strip().replace("/", "_").replace("\\", "_")
    name = _SAFE_NAME_RE.sub("_", name).strip(" ._")
    if not name or name in {".", ".."}:
        name = default
    if max_len > 0 and len(name) > max_len:
        # Keep extension if any.
        p = Path(name)
        stem = p.stem[: max(1, max_len - len(p.suffix))]
        name = f"{stem}{p.suffix}"
    return name

