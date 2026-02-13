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
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from openledger.stage_contracts import ART_REVIEW, ART_UNIFIED_WITH_ID, required_columns

from ._common import log, make_parser

REVIEW_REQUIRED_COLUMNS = set(required_columns(ART_REVIEW))
UNIFIED_WITH_ID_REQUIRED_COLUMNS = set(required_columns(ART_UNIFIED_WITH_ID))
WALLET_PRIMARY_SOURCES = {"wechat", "alipay"}
NORMALIZED_FLOWS = {"expense", "income", "refund", "transfer", "other", "repayment", "rebate"}


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


def _normalized_amount_key(value: object) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    try:
        return str(Decimal(s).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError):
        return s


def _row_richness_score(row: pd.Series) -> int:
    score_cols = [
        "item",
        "category",
        "pay_method",
        "remark",
        "match_status",
        "match_group_id",
    ]
    score = 0
    for col in score_cols:
        if str(row.get(col, "")).strip():
            score += 1
    return score


def _dedupe_unified_rows(unified: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if "txn_id" not in unified.columns:
        return unified, 0
    duplicated = unified["txn_id"].duplicated(keep=False)
    if not bool(duplicated.any()):
        return unified, 0

    dedup = unified.copy()
    dedup["_orig_idx"] = range(len(dedup))
    dedup["_row_score"] = dedup.apply(_row_richness_score, axis=1)
    dedup = dedup.sort_values(
        by=["txn_id", "_row_score", "_orig_idx"],
        ascending=[True, False, True],
        kind="stable",
    )
    dedup = dedup.drop_duplicates(subset=["txn_id"], keep="first")
    dropped = len(unified) - len(dedup)
    dedup = dedup.sort_values(by="_orig_idx", kind="stable").drop(columns=["_orig_idx", "_row_score"])
    return dedup, dropped


def _dedupe_review_rows(review: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if "txn_id" not in review.columns:
        return review, 0
    duplicated = review["txn_id"].duplicated(keep="last")
    dropped = int(duplicated.sum())
    if dropped <= 0:
        return review, 0
    return review.loc[~duplicated].copy(), dropped


def _auto_ignore_wallet_duplicates(merged: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    required_cols = [
        "match_group_id",
        "primary_source",
        "trade_date",
        "amount",
        "merchant",
        "item",
        "flow",
        "ignored",
        "ignore_reason",
    ]
    if any(col not in merged.columns for col in required_cols):
        return merged, 0

    group_index: dict[str, list[int]] = {}
    for idx, row in merged.iterrows():
        group_id = str(row.get("match_group_id", "")).strip()
        if not group_id:
            continue
        group_index.setdefault(group_id, []).append(idx)

    if not group_index:
        return merged, 0

    dropped = 0
    for _, indices in group_index.items():
        if len(indices) <= 1:
            continue

        bill_indices: list[int] = []
        wallet_indices: list[int] = []
        for idx in indices:
            primary_source = str(merged.at[idx, "primary_source"]).strip()
            if primary_source in WALLET_PRIMARY_SOURCES:
                wallet_indices.append(idx)
            else:
                bill_indices.append(idx)
        if not bill_indices or not wallet_indices:
            continue

        bill_signatures = {
            (
                str(merged.at[idx, "trade_date"]).strip(),
                _normalized_amount_key(merged.at[idx, "amount"]),
                str(merged.at[idx, "merchant"]).strip(),
                str(merged.at[idx, "item"]).strip(),
                str(merged.at[idx, "flow"]).strip(),
            )
            for idx in bill_indices
        }

        for idx in wallet_indices:
            ignored = _parse_bool(merged.at[idx, "ignored"])
            if ignored:
                continue
            signature = (
                str(merged.at[idx, "trade_date"]).strip(),
                _normalized_amount_key(merged.at[idx, "amount"]),
                str(merged.at[idx, "merchant"]).strip(),
                str(merged.at[idx, "item"]).strip(),
                str(merged.at[idx, "flow"]).strip(),
            )
            if signature not in bill_signatures:
                continue
            merged.at[idx, "ignored"] = "true"
            merged.at[idx, "ignore_reason"] = "自动去重：同一匹配组已保留账单侧，忽略钱包侧重复项"
            dropped += 1

    return merged, dropped


def _normalize_flow_value(flow: object, category_id: object, amount: object) -> str:
    raw_flow = str(flow or "").strip()
    if raw_flow in NORMALIZED_FLOWS:
        return raw_flow

    category = str(category_id or "").strip()
    if category == "refund":
        return "refund"

    amount_key = _normalized_amount_key(amount)
    if amount_key:
        try:
            amount_dec = Decimal(amount_key)
            if amount_dec > 0:
                return "income"
            if amount_dec < 0:
                return "expense"
        except (InvalidOperation, ValueError):
            pass
    return "other"


def _normalize_flows(merged: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if "flow" not in merged.columns:
        return merged, 0
    if "category_id" not in merged.columns:
        merged["category_id"] = ""
    if "amount" not in merged.columns:
        merged["amount"] = ""

    norm = merged.apply(
        lambda row: _normalize_flow_value(
            row.get("flow", ""),
            row.get("category_id", ""),
            row.get("amount", ""),
        ),
        axis=1,
    )
    changed = int((norm != merged["flow"].astype(str)).sum())
    merged["flow"] = norm
    return merged, changed


def _auto_ignore_missing_amount(merged: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if "amount" not in merged.columns:
        return merged, 0
    if "ignored" not in merged.columns:
        return merged, 0
    if "ignore_reason" not in merged.columns:
        merged["ignore_reason"] = ""

    ignored_bool = merged["ignored"].map(_parse_bool)
    amount_num = pd.to_numeric(merged["amount"], errors="coerce")
    missing_mask = amount_num.isna() & (~ignored_bool)
    dropped = int(missing_mask.sum())
    if dropped <= 0:
        return merged, 0

    merged.loc[missing_mask, "ignored"] = "true"
    current_reason = merged.loc[missing_mask, "ignore_reason"].astype(str).str.strip()
    fill_mask = current_reason == ""
    merged.loc[current_reason[fill_mask].index, "ignore_reason"] = "自动忽略：金额缺失"
    return merged, dropped


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

    missing_unified_cols = sorted(UNIFIED_WITH_ID_REQUIRED_COLUMNS - set(unified.columns))
    if missing_unified_cols:
        raise SystemExit(f"unified.with_id.csv 缺少列: {missing_unified_cols}")

    missing = sorted(REVIEW_REQUIRED_COLUMNS - set(review.columns))
    if missing:
        raise SystemExit(f"review.csv 缺少列: {missing}")

    unified, unified_dropped = _dedupe_unified_rows(unified)
    if unified_dropped:
        log("finalize", f"自动去重：unified 同 txn_id 重复行={unified_dropped}")

    review, review_dropped = _dedupe_review_rows(review)
    if review_dropped:
        log("finalize", f"自动去重：review 同 txn_id 重复行={review_dropped}")

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
    merged, auto_dropped = _auto_ignore_wallet_duplicates(merged)
    if auto_dropped:
        log("finalize", f"自动去重：match_group 钱包重复项={auto_dropped}")

    merged, flow_changed = _normalize_flows(merged)
    if flow_changed:
        log("finalize", f"flow 归一化行数={flow_changed}")

    merged, missing_amount_ignored = _auto_ignore_missing_amount(merged)
    if missing_amount_ignored:
        log("finalize", f"自动忽略：金额缺失行={missing_amount_ignored}")

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
    args = parser.parse_args()

    drop_cols = [c.strip() for c in args.drop_cols.split(",") if c.strip()]
    finalize(
        config_path=args.config,
        unified_with_id_csv=args.unified_with_id,
        review_csv=args.review,
        out_dir=args.out_dir,
        drop_cols=drop_cols,
        require_review=True,
    )


if __name__ == "__main__":
    main()
