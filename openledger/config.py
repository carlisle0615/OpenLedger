from __future__ import annotations

from pathlib import Path


def resolve_global_classifier_config(root: Path) -> Path:
    """
    优先使用本地覆盖配置（已被 gitignore）；否则回退到仓库提交的公共默认配置。
    """
    local_cfg = root / "config" / "classifier.local.json"
    if local_cfg.exists():
        return local_cfg
    return root / "config" / "classifier.json"


def global_classifier_write_path(root: Path) -> Path:
    """
    始终写入本地覆盖配置，避免误改动仓库内提交的公共默认配置。
    """
    return root / "config" / "classifier.local.json"
