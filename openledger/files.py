from __future__ import annotations

import re
from pathlib import Path


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\u4e00-\u9fff-]+")


def safe_filename(raw: str, *, default: str = "upload.bin", max_len: int = 180) -> str:
    """
    将用户提供的文件名（例如 multipart upload）转换为安全的 basename。

    - 去掉所有目录成分（只保留文件名）。
    - 移除控制字符与路径分隔符。
    - 将不安全字符折叠为下划线。
    - 防止出现仅由点组成的名字（如 '.'、'..'）。
    """
    name = str(raw or "").strip().replace("\x00", "")
    name = Path(name).name  # 去掉路径部分
    name = name.strip().replace("/", "_").replace("\\", "_")
    name = _SAFE_NAME_RE.sub("_", name).strip(" ._")
    if not name or name in {".", ".."}:
        name = default
    if max_len > 0 and len(name) > max_len:
        # 尽量保留扩展名。
        p = Path(name)
        stem = p.stem[: max(1, max_len - len(p.suffix))]
        name = f"{stem}{p.suffix}"
    return name
