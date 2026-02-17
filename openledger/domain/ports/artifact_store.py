from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class ArtifactStorePort(Protocol):
    def list_artifacts(self, run_id: str) -> list[dict[str, Any]]: ...

    def resolve_under_run(self, run_id: str, rel_path: str) -> Path: ...
