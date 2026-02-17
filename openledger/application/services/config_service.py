from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openledger.config import global_classifier_write_path, resolve_global_classifier_config
from openledger.infrastructure.workflow.runtime import make_paths


def read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("config must be a JSON object")
    return payload


def get_global_classifier_config(root: Path) -> dict[str, Any]:
    cfg_path = resolve_global_classifier_config(root)
    if not cfg_path.exists():
        raise FileNotFoundError("config not found")
    return read_json_object(cfg_path)


def update_global_classifier_config(root: Path, payload: dict[str, Any]) -> None:
    cfg_path = global_classifier_write_path(root)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def get_run_classifier_config(root: Path, run_id: str) -> dict[str, Any]:
    cfg = make_paths(root, run_id).config_dir / "classifier.json"
    if not cfg.exists():
        raise FileNotFoundError("config not found")
    return read_json_object(cfg)


def update_run_classifier_config(root: Path, run_id: str, payload: dict[str, Any]) -> None:
    cfg = make_paths(root, run_id).config_dir / "classifier.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
