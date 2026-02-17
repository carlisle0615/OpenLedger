from __future__ import annotations

from pathlib import Path
from typing import Any

from openledger.state import resolve_under_root
from openledger.infrastructure.workflow.runtime import list_artifacts, make_paths


class FileArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        return list_artifacts(make_paths(self.root, run_id))

    def resolve_under_run(self, run_id: str, rel_path: str) -> Path:
        run_dir = make_paths(self.root, run_id).run_dir
        return resolve_under_root(run_dir, rel_path)
