"""finalize：将审核结果合并为最终产物（明细 + 汇总）。

输入：
- `unified.with_id.csv`（来自 `classify` 阶段）
- `review.csv`（人工审核/编辑）
- 分类器配置（`config/classifier.json` 或 `config/classifier.local.json`）

输出：
- `<out-dir>/unified.transactions.categorized.csv`
- `<out-dir>/unified.transactions.categorized.xlsx`（两个 sheet：明细/汇总）
- `<out-dir>/category.summary.csv`
- `<out-dir>/pending_review.csv`（仅当仍需要人工审核时生成）
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ._common import log, make_parser


def default_classifier_config_path() -> Path:
    local = Path("config/classifier.local.json")
    if local.exists():
        return local
    return Path("config/classifier.json")


def _parse_bool(value: object) -> bool:
    if value is None:
        return False
    s = str(value).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    return False


def _read_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def finalize(
    config_path: Path,
    unified_with_id_csv: Path,
    review_csv: Path,
    out_dir: Path,
    drop_cols: list[str],
    require_review: bool,
) -> None:
    config = _read_config(config_path)
    categories = config.get("categories", [])
    category_map = {c["id"]: c.get("name", "") for c in categories if "id" in c}
    if "other" not in category_map:
        raise SystemExit("config.categories 必须包含 id=other。")

    out_dir.mkdir(parents=True, exist_ok=True)

    unified = pd.read_csv(unified_with_id_csv, dtype=str).fillna("")
    review = pd.read_csv(review_csv, dtype=str).fillna("")

    required_cols = {
        "txn_id",
        "suggested_category_id",
        "suggested_uncertain",
        "suggested_confidence",
        "suggested_note",
        "final_category_id",
        "final_note",
    }
    missing = sorted(required_cols - set(review.columns))
    if missing:
        raise SystemExit(f"review.csv 缺少列: {missing}")

    review["suggested_uncertain_bool"] = review["suggested_uncertain"].map(_parse_bool)
    review["final_category_id"] = review["final_category_id"].astype(str).str.strip()
    review["suggested_category_id"] = review["suggested_category_id"].astype(str).str.strip()

    has_final_ignored = "final_ignored" in review.columns
    has_suggested_ignored = "suggested_ignored" in review.columns
    if has_final_ignored:
        review["final_ignored_str"] = review["final_ignored"].astype(str).str.strip()
        review["final_ignored_bool"] = review["final_ignored_str"].map(_parse_bool)
    if has_suggested_ignored:
        review["suggested_ignored_bool"] = review["suggested_ignored"].map(_parse_bool)

    def pick_ignored(row: pd.Series) -> bool:
        if has_final_ignored and str(row.get("final_ignored_str", "")).strip() != "":
            return bool(row.get("final_ignored_bool", False))
        if has_suggested_ignored:
            return bool(row.get("suggested_ignored_bool", False))
        return False

    review["ignored_bool"] = review.apply(pick_ignored, axis=1)
    review["ignored"] = review["ignored_bool"].map(lambda b: "true" if bool(b) else "false")

    if "final_ignore_reason" in review.columns:
        review["final_ignore_reason"] = review["final_ignore_reason"].astype(str).str.strip()
    else:
        review["final_ignore_reason"] = ""
    if "suggested_ignore_reason" in review.columns:
        review["suggested_ignore_reason"] = review["suggested_ignore_reason"].astype(str).str.strip()
    else:
        review["suggested_ignore_reason"] = ""
    review["ignore_reason"] = review.apply(
        lambda r: (r["final_ignore_reason"] or r["suggested_ignore_reason"]),
        axis=1,
    )

    def pick_category(row: pd.Series) -> str:
        return row["final_category_id"] or row["suggested_category_id"] or "other"

    review["category_id"] = review.apply(pick_category, axis=1)
    valid_category_ids = set(category_map.keys())
    review["invalid_category_bool"] = ~review["category_id"].isin(valid_category_ids)
    if bool(review["invalid_category_bool"].any()):
        review["invalid_category_id"] = review.apply(
            lambda r: (r["category_id"] if bool(r["invalid_category_bool"]) else ""),
            axis=1,
        )
        # review.csv 生成后配置可能变更；对无效的 category_id 做兜底回退到 other。
        review.loc[review["invalid_category_bool"], "category_id"] = "other"
    else:
        review["invalid_category_id"] = ""

    if require_review:
        needs = review[
            (~review["ignored_bool"])
            & (
                (review["invalid_category_bool"])
                | (review["suggested_uncertain_bool"] & (review["final_category_id"] == ""))
            )
        ]
        if not needs.empty:
            pending_path = out_dir / "pending_review.csv"
            needs.to_csv(pending_path, index=False, encoding="utf-8")
            raise SystemExit(
                f"发现 {len(needs)} 行仍需人工确认（不确定/或 category_id 无效）。"
                f"请在 review.csv 中填写 final_category_id。待处理清单: {pending_path}"
            )

    review["category_name"] = review["category_id"].map(lambda cid: category_map.get(cid, ""))

    def pick_source(row: pd.Series) -> str:
        if str(row.get("final_category_id", "")).strip():
            return "manual"
        src = str(row.get("suggested_source", "")).strip()
        if src == "regex_category_rule":
            return "regex"
        if src:
            return src
        return "llm"

    review["category_source"] = review.apply(pick_source, axis=1)
    review["category_confidence"] = review["suggested_confidence"]
    review["category_uncertain"] = review.apply(
        lambda r: "" if r["category_source"] == "manual" else ("true" if r["suggested_uncertain_bool"] else "false"),
        axis=1,
    )
    review["category_note"] = review.apply(
        lambda r: (r["final_note"].strip() or r["suggested_note"].strip()),
        axis=1,
    )

    merged = unified.merge(
        review[
            [
                "txn_id",
                "category_id",
                "category_name",
                "category_source",
                "category_confidence",
                "category_uncertain",
                "category_note",
                "ignored",
                "ignore_reason",
            ]
        ],
        on="txn_id",
        how="left",
    )

    # 删列（来自命令行 + 配置）。
    drop_from_config = [c for c in config.get("drop_output_columns", []) if isinstance(c, str)]
    drops = {c.strip() for c in (drop_from_config + drop_cols) if c.strip()}
    for col in sorted(drops):
        if col in merged.columns:
            merged = merged.drop(columns=[col])

    detailed_csv = out_dir / "unified.transactions.categorized.csv"
    report_xlsx = out_dir / "unified.transactions.categorized.xlsx"
    merged.to_csv(detailed_csv, index=False, encoding="utf-8")

    # 按分类聚合汇总。
    agg = merged.copy()
    agg["amount_num"] = pd.to_numeric(agg.get("amount", ""), errors="coerce")
    if "flow" not in agg.columns:
        agg["flow"] = ""

    if "ignored" in agg.columns:
        agg["ignored_bool"] = agg["ignored"].map(_parse_bool)
        agg = agg[~agg["ignored_bool"]].copy()
    else:
        agg["ignored_bool"] = False

    def sum_where(flow_value: str) -> pd.Series:
        return (
            agg[agg["flow"] == flow_value]
            .groupby(["category_id", "category_name"], dropna=False)["amount_num"]
            .sum(min_count=1)
        )

    summary = (
        agg.groupby(["category_id", "category_name"], dropna=False)
        .agg(
            count=("amount_num", "size"),
            sum_amount=("amount_num", "sum"),
        )
        .reset_index()
    )
    for flow_value, col_name in [
        ("expense", "sum_expense"),
        ("income", "sum_income"),
        ("refund", "sum_refund"),
        ("transfer", "sum_transfer"),
    ]:
        s = sum_where(flow_value).reset_index().rename(columns={"amount_num": col_name})
        summary = summary.merge(s, on=["category_id", "category_name"], how="left")

    summary_csv = out_dir / "category.summary.csv"
    summary.to_csv(summary_csv, index=False, encoding="utf-8")

    # 单个 Excel 工作簿，包含两个 sheet（明细 + 汇总）。
    with pd.ExcelWriter(report_xlsx, engine="openpyxl") as writer:
        merged.to_excel(writer, index=False, sheet_name="明细")
        summary.to_excel(writer, index=False, sheet_name="汇总")

    # 清理历史遗留的 summary workbook，避免混淆/过期产物残留。
    legacy_summary_xlsx = out_dir / "category.summary.xlsx"
    try:
        legacy_summary_xlsx.unlink()
    except FileNotFoundError:
        pass

    log("finalize", f"Excel={report_xlsx}")
    log("finalize", f"明细CSV={detailed_csv}")
    log("finalize", f"汇总CSV={summary_csv}")


def main() -> None:
    parser = make_parser("合并审核结果，生成最终明细与汇总。")
    parser.add_argument(
        "--config",
        type=Path,
        default=default_classifier_config_path(),
        help="分类器配置路径（默认：优先使用 config/classifier.local.json）。",
    )
    parser.add_argument("--unified-with-id", type=Path, default=Path("output/classify/unified.with_id.csv"))
    parser.add_argument("--review", type=Path, default=Path("output/classify/review.csv"))
    parser.add_argument("--out-dir", type=Path, default=Path("output"))
    parser.add_argument("--drop-cols", type=str, default="")
    parser.add_argument("--allow-unreviewed", action="store_true")
    args = parser.parse_args()

    drop_cols = [c.strip() for c in args.drop_cols.split(",") if c.strip()]
    finalize(
        config_path=args.config,
        unified_with_id_csv=args.unified_with_id,
        review_csv=args.review,
        out_dir=args.out_dir,
        drop_cols=drop_cols,
        require_review=not args.allow_unreviewed,
    )


if __name__ == "__main__":
    main()
