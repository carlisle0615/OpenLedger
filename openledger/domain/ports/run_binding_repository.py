from __future__ import annotations

from typing import Any, Protocol


class RunBindingRepositoryPort(Protocol):
    def get_binding(self, run_id: str) -> dict[str, Any] | None: ...

    def set_binding(self, run_id: str, profile_id: str) -> dict[str, Any]: ...

    def clear_binding(self, run_id: str) -> None: ...
