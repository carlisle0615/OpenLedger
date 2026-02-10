from __future__ import annotations

from pathlib import Path


def resolve_global_classifier_config(root: Path) -> Path:
    """
    Prefer a local override (ignored by git) if present, otherwise fall back to
    the public default committed in the repo.
    """
    local_cfg = root / "config" / "classifier.local.json"
    if local_cfg.exists():
        return local_cfg
    return root / "config" / "classifier.json"


def global_classifier_write_path(root: Path) -> Path:
    """
    Always write to the local override to avoid accidentally modifying the
    committed default config.
    """
    return root / "config" / "classifier.local.json"

