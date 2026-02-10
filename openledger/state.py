from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(4)
    return f"{ts}_{suffix}"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_rel_path(root: Path, target: Path) -> str:
    return str(target.resolve().relative_to(root.resolve()))


def resolve_under_root(root: Path, rel_path: str) -> Path:
    p = (root / rel_path).resolve()
    root_resolved = root.resolve()
    if root_resolved == p:
        return p
    try:
        p.relative_to(root_resolved)
    except Exception as exc:
        raise ValueError("path escapes root") from exc
    return p


@dataclass(frozen=True)
class StageDef:
    id: str
    name: str


DEFAULT_STAGES: list[StageDef] = [
    StageDef("extract_pdf", "提取 PDF 交易"),
    StageDef("extract_exports", "解析微信/支付宝导出"),
    StageDef("match_credit_card", "信用卡 ↔ 明细匹配回填"),
    StageDef("match_bank", "借记卡流水 ↔ 明细匹配回填"),
    StageDef("build_unified", "生成统一抽象输出"),
    StageDef("classify", "LLM/规则 分类 + 生成审核表"),
    StageDef("finalize", "合并审核结果 + 聚合汇总"),
]


def init_run_state(run_id: str) -> dict[str, Any]:
    now_local = datetime.now().astimezone()
    return {
        "run_id": run_id,
        "name": "",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "status": "idle",
        "cancel_requested": False,
        "inputs": [],
        "options": {
            "classify_mode": "llm",  # llm | dry_run
            "allow_unreviewed": False,
            # Default to current year/month (credit-card cycle: prev month 21 ~ current month 20).
            "period_year": now_local.year,
            "period_month": now_local.month,
        },
        "current_stage": None,
        "stages": [
            {
                "id": s.id,
                "name": s.name,
                "status": "pending",
                "started_at": "",
                "ended_at": "",
                "log_path": f"logs/{s.id}.log",
                "error": "",
            }
            for s in DEFAULT_STAGES
        ],
    }
