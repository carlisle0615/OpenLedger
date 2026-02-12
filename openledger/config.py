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


def resolve_card_alias_config(root: Path) -> Path:
    """
    优先读取本地覆盖卡号映射；若不存在则回退到仓库默认映射。
    """
    local_cfg = root / "config" / "card_aliases.local.json"
    if local_cfg.exists():
        return local_cfg
    default_cfg = root / "config" / "card_aliases.json"
    if default_cfg.exists():
        return default_cfg
    return local_cfg


def card_alias_write_path(root: Path) -> Path:
    """
    始终写入本地覆盖卡号映射，避免误改仓库默认映射。
    """
    return root / "config" / "card_aliases.local.json"
