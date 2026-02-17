from __future__ import annotations

from pathlib import Path

from openledger.infrastructure.workflow.runtime import WorkflowRunner


class WorkflowExecutor:
    def __init__(self, root: Path) -> None:
        self._runner = WorkflowRunner(root)

    def start(
        self,
        run_id: str,
        *,
        stages: list[str] | None,
        options: dict[str, object] | None,
    ) -> None:
        self._runner.start(run_id, stages=stages, options=options)

    def request_cancel(self, run_id: str) -> None:
        self._runner.request_cancel(run_id)

    def is_running(self, run_id: str) -> bool:
        return self._runner.is_running(run_id)
