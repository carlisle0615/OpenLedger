"""build_unified：从多来源产物构建一张“统一抽象字段”的交易表。

输入（通常都在 `<out-dir>/` 下）：
- `credit_card.enriched.csv`, `credit_card.unmatched.csv`
- `bank.enriched.csv`, `bank.unmatched.csv`
- `wechat.normalized.csv`, `alipay.normalized.csv`

输出：
- `<out-dir>/unified.transactions.csv`
- `<out-dir>/unified.transactions.xlsx`
- 可选：指定账期筛选时会额外生成 `<out-dir>/unified.transactions.all.*`

示例：
- `uv run python scripts/build_unified_output.py --out-dir output`
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from _common import log, make_parser

UNIFIED_COLUMNS = [
    "trade_time",
    "trade_date",
    "post_date",
    "account",
    "currency",
    "amount",
    "amount_abs",
    "flow",
    "merchant",
    "item",
    "category",
    "pay_method",
    "primary_source",
    "sources",
    "match_status",
    "remark",
]


def _to_decimal(value: Any) -> Decimal:
    s = str(value).strip()
    s = s.replace("¥", "").replace("￥", "").replace(",", "").strip()
    if not s or s.lower() in {"nan", "none"}:
        raise ValueError(f"金额为空: {value!r}")
    try:
        return Decimal(s)
    except InvalidOperation as exc:  # pragma: no cover - 防御性分支
        raise ValueError(f"无效的金额: {value!r}") from exc


_CREDIT_LAST4_RE = re.compile(r"信用卡\((\d{4})\)")
_DEBIT_LAST4_RE = re.compile(r"储蓄卡\((\d{4})\)")


def _has_card_pay_method(pay_method: Any) -> bool:
    s = str(pay_method)
    return bool(_CREDIT_LAST4_RE.search(s) or _DEBIT_LAST4_RE.search(s))


def _is_refund_like(direction: str, item: str, status: str, category: str) -> bool:
    if "退款" in (item or "") or "退款" in (status or "") or "退款" in (category or ""):
        return True
    if direction in {"收入", "不计收支"}:
        return True
    return False


def _ensure_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df


def _read_csv_or_empty(path: Path, expected_cols: list[str]) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, dtype=str)
    except (FileNotFoundError, EmptyDataError):
        return pd.DataFrame(columns=expected_cols)
    return _ensure_cols(df, expected_cols)


def _empty_unified_df() -> pd.DataFrame:
    return pd.DataFrame(columns=UNIFIED_COLUMNS)


def _wechat_wallet_rows(wechat_norm: pd.DataFrame) -> pd.DataFrame:
    df = wechat_norm.copy()
    df = _ensure_cols(
        df,
        ["pay_method", "amount", "direction", "trans_time", "trans_date", "counterparty", "item", "trans_type", "status"],
    )
    if df.empty:
        return _empty_unified_df()
    df["is_card"] = df["pay_method"].map(_has_card_pay_method)
    wallet = df[~df["is_card"]].copy()
    if wallet.empty:
        return _empty_unified_df()
    wallet["primary_source"] = "wechat"
    wallet["account"] = "WeChat(" + wallet["pay_method"].fillna("").astype(str).str.strip().replace({"": "wallet"}) + ")"
    wallet["currency"] = "CNY"
    wallet["amount_dec"] = wallet["amount"].map(_to_decimal)
    wallet["amount_signed"] = wallet.apply(
        lambda r: (
            -abs(r["amount_dec"]) if r["direction"] == "支出" else abs(r["amount_dec"]) if r["direction"] == "收入" else abs(r["amount_dec"]) if _is_refund_like(r["direction"], r["item"], r["status"], r["trans_type"]) else None
        ),
        axis=1,
    )
    wallet["merchant"] = wallet["counterparty"].fillna("")
    wallet["item_best"] = wallet["item"].fillna("")
    wallet["category_best"] = wallet["trans_type"].fillna("")
    wallet["pay_method_best"] = wallet["pay_method"].fillna("")
    wallet["sources"] = "wechat"
    wallet["remark_unified"] = ""
    wallet["match_status"] = ""
    out = pd.DataFrame(
        {
            "trade_time": wallet["trans_time"].fillna(""),
            "trade_date": wallet["trans_date"].fillna(""),
            "post_date": "",
            "account": wallet["account"],
            "currency": wallet["currency"],
            "amount": wallet["amount_signed"].map(lambda v: "" if v is None else str(v)),
            "amount_abs": wallet["amount_dec"].map(lambda v: str(abs(v))),
            "flow": wallet.apply(
                lambda r: "refund" if _is_refund_like(r["direction"], r["item"], r["status"], r["trans_type"]) and r["direction"] != "支出" else "income" if r["direction"] == "收入" else "expense" if r["direction"] == "支出" else "other",
                axis=1,
            ),
            "merchant": wallet["merchant"],
            "item": wallet["item_best"],
            "category": wallet["category_best"],
            "pay_method": wallet["pay_method_best"],
            "primary_source": wallet["primary_source"],
            "sources": wallet["sources"],
            "match_status": wallet["match_status"],
            "remark": wallet["remark_unified"],
        }
    )
    return out


def _alipay_wallet_rows(alipay_norm: pd.DataFrame) -> pd.DataFrame:
    df = alipay_norm.copy()
    df = _ensure_cols(
        df,
        [
            "pay_method",
            "amount",
            "direction",
            "trans_time",
            "trans_date",
            "category",
            "counterparty",
            "counterparty_account",
            "item",
            "status",
        ],
    )
    if df.empty:
        return _empty_unified_df()
    df["is_card"] = df["pay_method"].map(_has_card_pay_method)
    wallet = df[~df["is_card"]].copy()
    if wallet.empty:
        return _empty_unified_df()
    wallet["primary_source"] = "alipay"
    wallet["account"] = "Alipay(" + wallet["pay_method"].fillna("").astype(str).str.strip().replace({"": "wallet"}) + ")"
    wallet["currency"] = "CNY"
    wallet["amount_dec"] = wallet["amount"].map(_to_decimal)
    wallet["amount_signed"] = wallet.apply(
        lambda r: (
            -abs(r["amount_dec"]) if r["direction"] == "支出" else abs(r["amount_dec"]) if r["direction"] == "收入" else abs(r["amount_dec"]) if _is_refund_like(r["direction"], r["item"], r["status"], r["category"]) else None
        ),
        axis=1,
    )
    wallet["merchant"] = wallet["counterparty"].fillna("")
    wallet["item_best"] = wallet["item"].fillna("")
    wallet["category_best"] = wallet["category"].fillna("")
    wallet["pay_method_best"] = wallet["pay_method"].fillna("")
    wallet["sources"] = "alipay"
    wallet["remark_unified"] = ""
    wallet["match_status"] = ""
    out = pd.DataFrame(
        {
            "trade_time": wallet["trans_time"].fillna(""),
            "trade_date": wallet["trans_date"].fillna(""),
            "post_date": "",
            "account": wallet["account"],
            "currency": wallet["currency"],
            "amount": wallet["amount_signed"].map(lambda v: "" if v is None else str(v)),
            "amount_abs": wallet["amount_dec"].map(lambda v: str(abs(v))),
            "flow": wallet.apply(
                lambda r: "refund" if _is_refund_like(r["direction"], r["item"], r["status"], r["category"]) and r["direction"] != "支出" else "income" if r["direction"] == "收入" else "expense" if r["direction"] == "支出" else "other",
                axis=1,
            ),
            "merchant": wallet["merchant"],
            "item": wallet["item_best"],
            "category": wallet["category_best"],
            "pay_method": wallet["pay_method_best"],
            "primary_source": wallet["primary_source"],
            "sources": wallet["sources"],
            "match_status": wallet["match_status"],
            "remark": wallet["remark_unified"],
        }
    )
    return out


def _credit_card_rows(cc_enriched: pd.DataFrame, cc_unmatched: pd.DataFrame) -> pd.DataFrame:
    cc = pd.concat([cc_enriched, cc_unmatched], ignore_index=True).fillna("")
    cc = _ensure_cols(
        cc,
        [
            "section",
            "trans_date",
            "post_date",
            "description",
            "amount_rmb",
            "card_last4",
            "match_status",
            "detail_trans_time",
            "detail_counterparty",
            "detail_item",
            "detail_category_or_type",
            "detail_pay_method",
            "detail_channel",
            "match_sources",
        ],
    )
    if cc.empty:
        return _empty_unified_df()
    cc["primary_source"] = "cmb_credit_card"
    cc["account"] = cc["card_last4"].map(lambda x: f"CMB CreditCard({str(x).strip() or '?'})")
    cc["currency"] = "CNY"
    cc["amount_dec"] = cc["amount_rmb"].map(_to_decimal)
    cc["amount_abs_dec"] = cc["amount_dec"].map(lambda d: abs(d))

    def flow(row: pd.Series) -> str:
        section = str(row.get("section", "")).strip()
        desc = str(row.get("description", "")).strip()
        if section == "消费":
            return "expense"
        if section == "退款":
            return "refund"
        if section == "还款":
            return "rebate" if "回馈金" in desc else "repayment"
        return section or "other"

    def signed_amount(row: pd.Series) -> Decimal:
        section = str(row.get("section", "")).strip()
        desc = str(row.get("description", "")).strip()
        amt = row["amount_dec"]
        abs_amt = abs(amt)
        if section == "消费":
            return -abs_amt
        if section == "退款":
            return abs_amt
        if section == "还款":
            return abs_amt if "回馈金" in desc else -abs_amt
        return -abs_amt if amt >= 0 else abs_amt

    cc["amount_signed"] = cc.apply(signed_amount, axis=1)
    cc["flow"] = cc.apply(flow, axis=1)

    cc["merchant"] = cc.apply(
        lambda r: (r.get("detail_counterparty") or "").strip() if r.get("match_status") == "matched" else (r.get("description") or "").strip(),
        axis=1,
    )
    cc["item_best"] = cc.apply(lambda r: (r.get("detail_item") or "").strip(), axis=1)
    cc["category_best"] = cc.apply(lambda r: (r.get("detail_category_or_type") or "").strip(), axis=1)
    cc["pay_method_best"] = cc.apply(lambda r: (r.get("detail_pay_method") or "").strip(), axis=1)

    cc["sources"] = cc.apply(
        lambda r: "cmb_credit_card|" + str(r.get("detail_channel")).strip() if r.get("match_status") == "matched" else "cmb_credit_card",
        axis=1,
    )
    cc["remark_unified"] = cc.apply(
        lambda r: (
            f"多源匹配：{r.get('match_sources')}"
            if r.get("match_status") == "matched"
            else f"未匹配明细：{r.get('match_status')}" if r.get("match_status") else ""
        ),
        axis=1,
    )

    out = pd.DataFrame(
        {
            "trade_time": cc["detail_trans_time"].fillna(""),
            "trade_date": cc["trans_date"].fillna(""),
            "post_date": cc["post_date"].fillna(""),
            "account": cc["account"],
            "currency": cc["currency"],
            "amount": cc["amount_signed"].map(str),
            "amount_abs": cc["amount_abs_dec"].map(lambda v: str(v)),
            "flow": cc["flow"],
            "merchant": cc["merchant"],
            "item": cc["item_best"],
            "category": cc["category_best"],
            "pay_method": cc["pay_method_best"],
            "primary_source": cc["primary_source"],
            "sources": cc["sources"],
            "match_status": cc.get("match_status", "").fillna(""),
            "remark": cc["remark_unified"],
        }
    )
    return out


def _bank_rows(bank_enriched: pd.DataFrame, bank_unmatched: pd.DataFrame) -> pd.DataFrame:
    bank = pd.concat([bank_enriched, bank_unmatched], ignore_index=True).fillna("")
    bank = _ensure_cols(
        bank,
        [
            "account_last4",
            "trans_date",
            "currency",
            "amount",
            "summary",
            "counterparty",
            "match_status",
            "detail_trans_time",
            "detail_counterparty",
            "detail_item",
            "detail_category_or_type",
            "detail_pay_method",
            "detail_channel",
            "match_sources",
        ],
    )
    if bank.empty:
        return _empty_unified_df()
    bank["primary_source"] = "cmb_statement"
    bank["account"] = bank["account_last4"].map(lambda x: f"CMB Debit({str(x).strip() or '?'})")
    bank["currency"] = bank.get("currency", "CNY").fillna("CNY")
    bank["amount_dec"] = bank["amount"].map(_to_decimal)
    bank["amount_abs_dec"] = bank["amount_dec"].map(lambda d: abs(d))

    def flow(row: pd.Series) -> str:
        summary = str(row.get("summary", "")).strip()
        amt: Decimal = row["amount_dec"]
        if "退款" in summary and amt > 0:
            return "refund"
        if "支付" in summary and amt < 0:
            return "expense"
        if "转账" in summary or "转入" in summary or "转出" in summary:
            return "transfer"
        return summary or "other"

    bank["flow"] = bank.apply(flow, axis=1)

    bank["merchant"] = bank.apply(
        lambda r: (r.get("detail_counterparty") or "").strip() if r.get("match_status") == "matched" else (r.get("counterparty") or "").strip(),
        axis=1,
    )
    bank["item_best"] = bank.apply(lambda r: (r.get("detail_item") or "").strip(), axis=1)
    bank["category_best"] = bank.apply(
        lambda r: (r.get("detail_category_or_type") or "").strip() if r.get("match_status") == "matched" else (r.get("summary") or "").strip(),
        axis=1,
    )
    bank["pay_method_best"] = bank.apply(lambda r: (r.get("detail_pay_method") or "").strip(), axis=1)

    bank["sources"] = bank.apply(
        lambda r: "cmb_statement|" + str(r.get("detail_channel")).strip() if r.get("match_status") == "matched" else "cmb_statement",
        axis=1,
    )
    bank["remark_unified"] = bank.apply(
        lambda r: (
            f"多源匹配：{r.get('match_sources')}"
            if r.get("match_status") == "matched"
            else f"未匹配明细：{r.get('match_status')}" if r.get("match_status") else ""
        ),
        axis=1,
    )

    out = pd.DataFrame(
        {
            "trade_time": bank["detail_trans_time"].fillna(""),
            "trade_date": bank["trans_date"].fillna(""),
            "post_date": "",
            "account": bank["account"],
            "currency": bank["currency"],
            "amount": bank["amount_dec"].map(str),
            "amount_abs": bank["amount_abs_dec"].map(lambda v: str(v)),
            "flow": bank["flow"],
            "merchant": bank["merchant"],
            "item": bank["item_best"],
            "category": bank["category_best"],
            "pay_method": bank["pay_method_best"],
            "primary_source": bank["primary_source"],
            "sources": bank["sources"],
            "match_status": bank.get("match_status", "").fillna(""),
            "remark": bank["remark_unified"],
        }
    )
    return out


def build_unified(
    cc_enriched_path: Path,
    cc_unmatched_path: Path,
    bank_enriched_path: Path,
    bank_unmatched_path: Path,
    wechat_norm_path: Path,
    alipay_norm_path: Path,
    out_dir: Path,
) -> Path:
    cc_required = ["section", "trans_date", "post_date", "description", "amount_rmb", "card_last4", "match_status"]
    bank_required = ["account_last4", "trans_date", "currency", "amount", "summary", "counterparty", "match_status"]
    wechat_required = ["pay_method", "amount", "direction", "trans_time", "trans_date", "trans_type", "counterparty", "item", "status"]
    alipay_required = [
        "pay_method",
        "amount",
        "direction",
        "trans_time",
        "trans_date",
        "category",
        "counterparty",
        "counterparty_account",
        "item",
        "status",
    ]

    cc_enriched = _read_csv_or_empty(cc_enriched_path, cc_required)
    cc_unmatched = _read_csv_or_empty(cc_unmatched_path, cc_required)
    bank_enriched = _read_csv_or_empty(bank_enriched_path, bank_required)
    bank_unmatched = _read_csv_or_empty(bank_unmatched_path, bank_required)
    wechat_norm = _read_csv_or_empty(wechat_norm_path, wechat_required)
    alipay_norm = _read_csv_or_empty(alipay_norm_path, alipay_required)

    cc_out = _credit_card_rows(cc_enriched, cc_unmatched)
    bank_out = _bank_rows(bank_enriched, bank_unmatched)
    wallet_out = pd.concat([_wechat_wallet_rows(wechat_norm), _alipay_wallet_rows(alipay_norm)], ignore_index=True)

    all_txn = pd.concat([cc_out, bank_out, wallet_out], ignore_index=True)
    # 先按日期、再按时间排序（时间可能为空）。
    all_txn = all_txn.sort_values(by=["trade_date", "trade_time", "account"], ascending=True, kind="stable")

    out_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = out_dir / "unified.transactions.xlsx"
    csv_path = out_dir / "unified.transactions.csv"

    all_xlsx_path = out_dir / "unified.transactions.all.xlsx"
    all_csv_path = out_dir / "unified.transactions.all.csv"

    filtered_txn = all_txn

    if getattr(build_unified, "_period", None):
        start_date, end_date, label = build_unified._period  # type: ignore[attr-defined]
        all_txn.to_csv(all_csv_path, index=False, encoding="utf-8")
        with pd.ExcelWriter(all_xlsx_path, engine="openpyxl") as writer:
            all_txn.to_excel(writer, index=False, sheet_name="transactions")

        all_txn["trade_date_dt"] = pd.to_datetime(all_txn["trade_date"], errors="coerce").dt.date
        mask = (all_txn["trade_date_dt"] >= start_date) & (all_txn["trade_date_dt"] <= end_date)
        filtered_txn = all_txn[mask].drop(columns=["trade_date_dt"]).copy()
        filtered_txn = filtered_txn.sort_values(by=["trade_date", "trade_time", "account"], ascending=True, kind="stable")
        log("build_unified", f"账期={label} 开始={start_date.isoformat()} 结束={end_date.isoformat()}")
        log("build_unified", f"全量行数={len(all_txn)} 筛选后行数={len(filtered_txn)}")

    filtered_txn.to_csv(csv_path, index=False, encoding="utf-8")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        filtered_txn.to_excel(writer, index=False, sheet_name="transactions")

    log("build_unified", f"行数={len(filtered_txn)} 输出={xlsx_path}")
    log("build_unified", f"行数={len(filtered_txn)} 输出={csv_path}")
    if getattr(build_unified, "_period", None):
        log("build_unified", f"全量输出={all_xlsx_path}")
        log("build_unified", f"全量输出={all_csv_path}")
    return xlsx_path


def main() -> None:
    parser = make_parser("生成统一抽象字段的单表输出文件。")
    parser.add_argument("--out-dir", type=Path, default=Path("output"))
    parser.add_argument("--cc-enriched", type=Path, default=Path("output/credit_card.enriched.csv"))
    parser.add_argument("--cc-unmatched", type=Path, default=Path("output/credit_card.unmatched.csv"))
    parser.add_argument("--bank-enriched", type=Path, default=Path("output/bank.enriched.csv"))
    parser.add_argument("--bank-unmatched", type=Path, default=Path("output/bank.unmatched.csv"))
    parser.add_argument("--wechat", type=Path, default=Path("output/wechat.normalized.csv"))
    parser.add_argument("--alipay", type=Path, default=Path("output/alipay.normalized.csv"))
    parser.add_argument("--period-year", type=int, default=None)
    parser.add_argument("--period-month", type=int, default=None)
    args = parser.parse_args()

    if hasattr(build_unified, "_period"):
        delattr(build_unified, "_period")  # type: ignore[attr-defined]

    if args.period_year and args.period_month:
        year = int(args.period_year)
        month = int(args.period_month)
        if not (1 <= month <= 12):
            raise SystemExit("--period-month 必须在 1~12 之间")
        start_year, start_month = (year - 1, 12) if month == 1 else (year, month - 1)
        start_date = date(start_year, start_month, 21)
        end_date = date(year, month, 20)
        # 临时挂到函数对象上，避免改动函数签名过大。
        build_unified._period = (start_date, end_date, f"{year:04d}-{month:02d}")  # type: ignore[attr-defined]

    build_unified(
        cc_enriched_path=args.cc_enriched,
        cc_unmatched_path=args.cc_unmatched,
        bank_enriched_path=args.bank_enriched,
        bank_unmatched_path=args.bank_unmatched,
        wechat_norm_path=args.wechat,
        alipay_norm_path=args.alipay,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    main()
