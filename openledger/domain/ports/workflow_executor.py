from __future__ import annotations

from typing import Any, Protocol


class WorkflowExecutorPort(Protocol):
    def start(
        self,
        run_id: str,
        *,
        stages: list[str] | None,
        options: dict[str, object] | None,
    ) -> None: ...

    def request_cancel(self, run_id: str) -> None: ...

    def is_running(self, run_id: str) -> bool: ...
