from __future__ import annotations

from pathlib import Path
from typing import Any

from openledger.infrastructure.workflow.runtime import (
    create_run,
    get_state,
    list_runs,
    make_paths,
    save_state,
)


class FileRunStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list_runs(self) -> list[str]:
        return list_runs(self.root)

    def create_run(self) -> str:
        return create_run(self.root).run_dir.name

    def get_state(self, run_id: str) -> dict[str, Any]:
        return get_state(make_paths(self.root, run_id))

    def save_state(self, run_id: str, state: dict[str, Any]) -> None:
        save_state(make_paths(self.root, run_id), state)

    def run_paths(self, run_id: str):
        return make_paths(self.root, run_id)
