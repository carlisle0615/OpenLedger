from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Any

from openledger.infrastructure.workflow.subprocess_executor import WorkflowExecutor
from openledger.infrastructure.workflow.runtime import get_state, make_paths, save_state


class WorkflowService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.executor = WorkflowExecutor(root)

    def start(
        self,
        run_id: str,
        *,
        stages: list[str] | None,
        options: dict[str, object] | None,
    ) -> None:
        self.executor.start(run_id, stages=stages, options=options)

    def cancel(self, run_id: str) -> None:
        self.executor.request_cancel(run_id)

    def is_running(self, run_id: str) -> bool:
        return self.executor.is_running(run_id)

    def reset_classify(self, run_id: str) -> None:
        if self.executor.is_running(run_id):
            raise RuntimeError("run is running")

        paths = make_paths(self.root, run_id)
        state = get_state(paths)

        shutil.rmtree(paths.out_dir / "classify", ignore_errors=True)
        for artifact in [
            paths.out_dir / "unified.transactions.categorized.csv",
            paths.out_dir / "unified.transactions.categorized.xlsx",
            paths.out_dir / "category.summary.csv",
            paths.out_dir / "category.summary.xlsx",
            paths.out_dir / "pending_review.csv",
        ]:
            try:
                artifact.unlink()
            except FileNotFoundError:
                pass

        for stage in state.get("stages", []):
            stage_id = str(stage.get("id", ""))
            if stage_id in {"classify", "finalize"}:
                stage["status"] = "pending"
                stage["started_at"] = ""
                stage["ended_at"] = ""
                stage["error"] = ""

        state["status"] = "idle"
        state["current_stage"] = None
        state["cancel_requested"] = False
        save_state(paths, state)

    def apply_review_updates(self, run_id: str, updates: list[dict[str, Any]]) -> int:
        paths = make_paths(self.root, run_id)
        review_path = paths.out_dir / "classify" / "review.csv"
        if not review_path.exists():
            raise FileNotFoundError("review.csv not found")

        update_map: dict[str, dict[str, Any]] = {}
        for update_item in updates:
            txn_id = str(update_item.get("txn_id", "")).strip()
            if txn_id:
                update_map[txn_id] = update_item
        temp_path = review_path.with_suffix(".csv.tmp")

        with review_path.open("r", encoding="utf-8", newline="") as f_in:
            reader = csv.DictReader(f_in)
            fieldnames = [str(name) for name in (reader.fieldnames or [])]
            if "txn_id" not in fieldnames:
                raise ValueError("review.csv missing txn_id")
            rows = list(reader)

        editable_fields = {
            "final_category_id",
            "final_note",
            "final_ignored",
            "final_ignore_reason",
        }
        editable_fields = {name for name in editable_fields if name in set(fieldnames)}

        for row in rows:
            txn_id = str(row.get("txn_id", "") or "").strip()
            if txn_id not in update_map:
                continue
            update_item = update_map[txn_id]
            for key in editable_fields:
                value = update_item.get(key)
                if value is None:
                    continue
                row[key] = str(value)

        with temp_path.open("w", encoding="utf-8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        temp_path.replace(review_path)
        return len(update_map)
