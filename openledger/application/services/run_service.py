from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any, Literal

from openledger.files import safe_filename
from openledger.infrastructure.persistence.sqla.profile_store import get_run_binding
from openledger.infrastructure.workflow.runtime import (
    create_run,
    get_state,
    list_artifacts,
    list_runs,
    make_paths,
    save_state,
)


def list_runs_payload(root: Path) -> dict[str, Any]:
    run_ids = list_runs(root)
    runs_meta: list[dict[str, Any]] = []
    for run_id in run_ids:
        state = get_state(make_paths(root, run_id))
        runs_meta.append(
            {
                "id": run_id,
                "name": str(state.get("name", "") or ""),
                "status": str(state.get("status", "") or ""),
                "created_at": str(state.get("created_at", "") or ""),
            }
        )
    return {"runs": run_ids, "runs_meta": runs_meta}


def get_run_state(root: Path, run_id: str) -> dict[str, Any]:
    paths = make_paths(root, run_id)
    state_payload = get_state(paths)
    try:
        state_payload["profile_binding"] = get_run_binding(root, run_id)
    except FileNotFoundError:
        state_payload["profile_binding"] = None
    return state_payload


def create_run_state(root: Path, *, name: str = "") -> dict[str, Any]:
    paths = create_run(root)
    run_id = paths.run_dir.name
    run_name = str(name or "").strip()[:80]
    if run_name:
        state = get_state(paths)
        state["name"] = run_name
        save_state(paths, state)
    return get_run_state(root, run_id)


def list_run_artifacts(root: Path, run_id: str) -> list[dict[str, Any]]:
    return list_artifacts(make_paths(root, run_id))


def update_run_options(
    root: Path, run_id: str, options_payload: dict[str, Any]
) -> None:
    paths = make_paths(root, run_id)
    state = get_state(paths)
    options = dict(state.get("options", {}))
    options.update(options_payload)
    state["options"] = options
    save_state(paths, state)


def save_upload_files(
    root: Path, run_id: str, files: list[Any]
) -> list[dict[str, Any]]:
    paths = make_paths(root, run_id)
    if not paths.run_dir.exists():
        raise FileNotFoundError("run not found")
    paths.inputs_dir.mkdir(parents=True, exist_ok=True)

    def pick_unique_name(name: str) -> str:
        dst = paths.inputs_dir / name
        if not dst.exists():
            return name
        stem = Path(name).stem
        suffix = Path(name).suffix
        for index in range(1, 1000):
            candidate = f"{stem}_{index}{suffix}"
            if not (paths.inputs_dir / candidate).exists():
                return candidate
        return f"{stem}_{os.getpid()}{suffix}"

    saved: list[dict[str, Any]] = []
    for upload in files:
        filename = getattr(upload, "filename", "")
        if not filename:
            continue
        safe_name = safe_filename(filename, default="upload.bin")
        target_name = pick_unique_name(safe_name)
        target_path = paths.inputs_dir / target_name
        file_obj = getattr(upload, "file")
        target_path.write_bytes(file_obj.read())
        saved.append(
            {
                "name": target_name,
                "path": f"inputs/{target_name}",
                "size": target_path.stat().st_size,
            }
        )
    state = get_state(paths)
    state["inputs"] = saved
    save_state(paths, state)
    return saved


def _file_item(run_dir: Path, file_path: Path) -> dict[str, Any]:
    rel = str(file_path.resolve().relative_to(run_dir.resolve()))
    if file_path.exists() and file_path.is_file():
        size = file_path.stat().st_size
    else:
        size = None
    return {
        "path": rel,
        "name": file_path.name,
        "exists": file_path.exists(),
        "size": size,
    }


def _glob_items(run_dir: Path, base: Path, pattern: str) -> list[dict[str, Any]]:
    return [_file_item(run_dir, p) for p in sorted(base.glob(pattern)) if p.is_file()]


def _one_item(run_dir: Path, p: Path) -> list[dict[str, Any]]:
    return [_file_item(run_dir, p)]


def get_stage_io(root: Path, run_id: str, stage_id: str) -> dict[str, Any]:
    paths = make_paths(root, run_id)
    run_dir = paths.run_dir
    inputs_dir = paths.inputs_dir
    out_dir = paths.out_dir
    cfg_dir = paths.config_dir

    if stage_id == "extract_pdf":
        return {
            "stage_id": stage_id,
            "inputs": _glob_items(run_dir, inputs_dir, "*.pdf"),
            "outputs": _glob_items(run_dir, out_dir, "*.transactions.csv"),
        }

    if stage_id == "extract_exports":
        return {
            "stage_id": stage_id,
            "inputs": _glob_items(run_dir, inputs_dir, "*.xlsx")
            + _glob_items(run_dir, inputs_dir, "*.csv"),
            "outputs": _one_item(run_dir, out_dir / "wechat.normalized.csv")
            + _one_item(run_dir, out_dir / "alipay.normalized.csv"),
        }

    if stage_id == "match_credit_card":
        cc_candidates = _glob_items(run_dir, out_dir, "*信用卡*.transactions.csv")
        if not cc_candidates:
            cc_candidates = _glob_items(run_dir, out_dir, "*.transactions.csv")
        return {
            "stage_id": stage_id,
            "inputs": cc_candidates[:1]
            + _one_item(run_dir, out_dir / "wechat.normalized.csv")
            + _one_item(run_dir, out_dir / "alipay.normalized.csv"),
            "outputs": _one_item(run_dir, out_dir / "credit_card.enriched.csv")
            + _one_item(run_dir, out_dir / "credit_card.unmatched.csv")
            + _one_item(run_dir, out_dir / "credit_card.match.xlsx")
            + _one_item(run_dir, out_dir / "credit_card.match_debug.csv"),
        }

    if stage_id == "match_bank":
        bank_candidates = _glob_items(run_dir, out_dir, "*交易流水*.transactions.csv")
        if not bank_candidates:
            bank_candidates = _glob_items(run_dir, out_dir, "*.transactions.csv")
        return {
            "stage_id": stage_id,
            "inputs": bank_candidates
            + _one_item(run_dir, out_dir / "wechat.normalized.csv")
            + _one_item(run_dir, out_dir / "alipay.normalized.csv"),
            "outputs": _one_item(run_dir, out_dir / "bank.enriched.csv")
            + _one_item(run_dir, out_dir / "bank.unmatched.csv")
            + _one_item(run_dir, out_dir / "bank.match.xlsx")
            + _one_item(run_dir, out_dir / "bank.match_debug.csv"),
        }

    if stage_id == "build_unified":
        return {
            "stage_id": stage_id,
            "inputs": _one_item(run_dir, out_dir / "credit_card.enriched.csv")
            + _one_item(run_dir, out_dir / "credit_card.unmatched.csv")
            + _one_item(run_dir, out_dir / "bank.enriched.csv")
            + _one_item(run_dir, out_dir / "bank.unmatched.csv")
            + _one_item(run_dir, out_dir / "wechat.normalized.csv")
            + _one_item(run_dir, out_dir / "alipay.normalized.csv"),
            "outputs": _one_item(run_dir, out_dir / "unified.transactions.csv")
            + _one_item(run_dir, out_dir / "unified.transactions.xlsx")
            + _one_item(run_dir, out_dir / "unified.transactions.all.csv")
            + _one_item(run_dir, out_dir / "unified.transactions.all.xlsx"),
        }

    if stage_id == "classify":
        classify_outputs = (
            _glob_items(run_dir, out_dir / "classify", "**/*")
            if (out_dir / "classify").exists()
            else []
        )
        return {
            "stage_id": stage_id,
            "inputs": _one_item(run_dir, out_dir / "unified.transactions.csv")
            + _one_item(run_dir, cfg_dir / "classifier.json"),
            "outputs": classify_outputs,
        }

    if stage_id == "finalize":
        return {
            "stage_id": stage_id,
            "inputs": _one_item(run_dir, out_dir / "classify" / "unified.with_id.csv")
            + _one_item(run_dir, out_dir / "classify" / "review.csv")
            + _one_item(run_dir, cfg_dir / "classifier.json"),
            "outputs": _one_item(
                run_dir, out_dir / "unified.transactions.categorized.csv"
            )
            + _one_item(run_dir, out_dir / "unified.transactions.categorized.xlsx")
            + _one_item(run_dir, out_dir / "category.summary.csv")
            + _one_item(run_dir, out_dir / "pending_review.csv"),
        }

    return {"stage_id": stage_id, "inputs": [], "outputs": []}


def _count_csv_rows(
    path: Path, status_key: str = "match_status"
) -> tuple[int, dict[str, int]]:
    if not path.exists() or not path.is_file():
        return 0, {}
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        has_status = status_key in fieldnames
        count = 0
        reasons: dict[str, int] = {}
        for row in reader:
            count += 1
            if not has_status:
                continue
            status_value = str(row.get(status_key, "") or "").strip() or "unknown"
            reasons[status_value] = reasons.get(status_value, 0) + 1
    return count, reasons


def get_match_stats(
    root: Path,
    run_id: str,
    *,
    stage: Literal["match_credit_card", "match_bank"],
) -> dict[str, Any]:
    paths = make_paths(root, run_id)
    if stage == "match_credit_card":
        matched_path = paths.out_dir / "credit_card.enriched.csv"
        unmatched_path = paths.out_dir / "credit_card.unmatched.csv"
    else:
        matched_path = paths.out_dir / "bank.enriched.csv"
        unmatched_path = paths.out_dir / "bank.unmatched.csv"

    matched_count, _ = _count_csv_rows(matched_path)
    unmatched_count, unmatched_reasons = _count_csv_rows(unmatched_path)
    total = matched_count + unmatched_count
    match_rate = round(matched_count / total, 4) if total else 0.0
    reasons_sorted = sorted(
        unmatched_reasons.items(), key=lambda item: (-item[1], item[0])
    )
    reasons = [{"reason": key, "count": value} for key, value in reasons_sorted]
    return {
        "stage_id": stage,
        "matched": matched_count,
        "unmatched": unmatched_count,
        "total": total,
        "match_rate": match_rate,
        "unmatched_reasons": reasons,
    }
