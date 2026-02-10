"""工具：按日期批量忽略 review.csv 中的行。

该脚本用于大数据量场景的辅助操作，不属于默认流水线阶段。
它会原地修改 `review.csv`（可选生成 `.bak` 备份）。
"""

from __future__ import annotations

import csv
import shutil
from datetime import date
from pathlib import Path

from _common import log, make_parser

def _parse_date(value: object) -> date | None:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def main() -> None:
    parser = make_parser("当 trade_date < cutoff 时，将对应行批量标记为 ignored。")
    parser.add_argument(
        "--review",
        type=Path,
        required=True,
        help="review.csv 路径（例如：runs/<run_id>/output/classify/review.csv）",
    )
    parser.add_argument(
        "--cutoff",
        type=str,
        required=True,
        help="截止日期（YYYY-MM-DD）。trade_date < cutoff 的行会被忽略。",
    )
    parser.add_argument(
        "--note",
        type=str,
        default="跳过去年",
        help="写入 final_note 的值。",
    )
    parser.add_argument(
        "--reason",
        type=str,
        default="跳过去年",
        help="写入 final_ignore_reason 的值。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印命中/修改数量，不落盘修改文件。",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="写回前不创建 .bak 备份文件。",
    )
    args = parser.parse_args()

    cutoff = date.fromisoformat(args.cutoff)
    review_path: Path = args.review
    if not review_path.exists():
        raise SystemExit(f"review.csv 不存在: {review_path}")

    with review_path.open("r", encoding="utf-8", newline="") as f_in:
        reader = csv.DictReader(f_in)
        fieldnames = list(reader.fieldnames or [])
        if "txn_id" not in fieldnames:
            raise SystemExit("review.csv 缺少 txn_id 列。")
        if "trade_date" not in fieldnames:
            raise SystemExit("review.csv 缺少 trade_date 列。")
        rows = list(reader)

    # 确保可编辑字段存在。
    for col in ["final_ignored", "final_note", "final_ignore_reason"]:
        if col not in fieldnames:
            fieldnames.append(col)

    matched = 0
    changed = 0
    for row in rows:
        dt = _parse_date(row.get("trade_date", ""))
        if dt is None:
            continue
        if dt >= cutoff:
            continue

        matched += 1
        before = (row.get("final_ignored", ""), row.get("final_note", ""), row.get("final_ignore_reason", ""))
        row["final_ignored"] = "true"
        row["final_note"] = args.note
        row["final_ignore_reason"] = args.reason
        after = (row.get("final_ignored", ""), row.get("final_note", ""), row.get("final_ignore_reason", ""))
        if before != after:
            changed += 1

    log("batch_ignore", f"命中={matched} 修改={changed} 截止={cutoff.isoformat()}")
    if args.dry_run:
        return

    if not args.no_backup:
        backup = review_path.with_name(review_path.name + ".bak")
        shutil.copyfile(review_path, backup)
        log("batch_ignore", f"备份={backup}")

    tmp_path = review_path.with_suffix(".csv.tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(review_path)
    log("batch_ignore", f"已更新={review_path}")


if __name__ == "__main__":
    main()
