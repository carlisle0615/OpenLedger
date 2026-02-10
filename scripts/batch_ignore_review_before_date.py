from __future__ import annotations

import argparse
import csv
import shutil
from datetime import date
from pathlib import Path


def _parse_date(value: object) -> date | None:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch mark rows in review.csv as ignored when trade_date < cutoff."
    )
    parser.add_argument(
        "--review",
        type=Path,
        required=True,
        help="Path to review.csv (e.g. runs/<run_id>/output/classify/review.csv)",
    )
    parser.add_argument(
        "--cutoff",
        type=str,
        required=True,
        help="Cutoff date in YYYY-MM-DD. Rows with trade_date < cutoff will be ignored.",
    )
    parser.add_argument(
        "--note",
        type=str,
        default="跳过去年",
        help="Value to write into final_note for matched rows.",
    )
    parser.add_argument(
        "--reason",
        type=str,
        default="跳过去年",
        help="Value to write into final_ignore_reason for matched rows.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print matched/changed counts; do not modify file.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a .bak file before writing.",
    )
    args = parser.parse_args()

    cutoff = date.fromisoformat(args.cutoff)
    review_path: Path = args.review
    if not review_path.exists():
        raise SystemExit(f"review.csv not found: {review_path}")

    with review_path.open("r", encoding="utf-8", newline="") as f_in:
        reader = csv.DictReader(f_in)
        fieldnames = list(reader.fieldnames or [])
        if "txn_id" not in fieldnames:
            raise SystemExit("review.csv missing txn_id column.")
        if "trade_date" not in fieldnames:
            raise SystemExit("review.csv missing trade_date column.")
        rows = list(reader)

    # Ensure editable fields exist
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

    print(f"[batch_ignore_review_before_date] matched={matched} changed={changed} cutoff={cutoff.isoformat()}")
    if args.dry_run:
        return

    if not args.no_backup:
        backup = review_path.with_name(review_path.name + ".bak")
        shutil.copyfile(review_path, backup)
        print(f"[batch_ignore_review_before_date] backup -> {backup}")

    tmp_path = review_path.with_suffix(".csv.tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(review_path)
    print(f"[batch_ignore_review_before_date] updated -> {review_path}")


if __name__ == "__main__":
    main()

