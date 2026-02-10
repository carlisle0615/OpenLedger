from __future__ import annotations

import argparse
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from rapidfuzz import fuzz


def _to_decimal(value: Any) -> Decimal:
    s = str(value).strip()
    s = s.replace("¥", "").replace("￥", "").replace(",", "").strip()
    if s in {"", "nan", "NaN", "None"}:
        raise ValueError(f"Empty decimal: {value!r}")
    try:
        return Decimal(s)
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid decimal: {value!r}") from exc


def _to_date(value: Any) -> date | None:
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    return date.fromisoformat(s)


DEBIT_LAST4_RE = re.compile(r"储蓄卡\((\d{4})\)")


def _extract_debit_last4(pay_method: Any) -> str | None:
    m = DEBIT_LAST4_RE.search(str(pay_method))
    return m.group(1) if m else None


def _is_refund_detail(detail_row: pd.Series) -> bool:
    direction = str(detail_row.get("direction", "")).strip()
    status = str(detail_row.get("status", "")).strip()
    item = str(detail_row.get("item", "")).strip()
    category_or_type = str(detail_row.get("category_or_type", "")).strip()
    if "退款" in status or "退款" in item or "退款" in category_or_type:
        return True
    if direction in {"收入", "不计收支"}:
        return True
    return False


def _direction_penalty(is_refund: bool, bank_amount: Decimal, detail_row: pd.Series) -> int:
    direction = str(detail_row.get("direction", "")).strip()
    if bank_amount < 0:
        return 0 if direction == "支出" else 2
    if is_refund:
        return 0 if _is_refund_detail(detail_row) else 2
    return 0 if direction == "收入" else 2


def _build_detail_df(wechat_path: Path, alipay_path: Path) -> pd.DataFrame:
    w = pd.read_csv(wechat_path, dtype=str)
    a = pd.read_csv(alipay_path, dtype=str)

    def norm(df: pd.DataFrame, channel: str) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)
        out["channel"] = channel
        out["trans_time"] = df.get("trans_time", "")
        out["trans_date"] = df.get("trans_date", "")
        out["direction"] = df.get("direction", "")
        out["amount"] = df.get("amount", "")
        out["pay_method"] = df.get("pay_method", "")
        out["counterparty"] = df.get("counterparty", "")
        out["item"] = df.get("item", "")
        out["trade_no"] = df.get("trade_no", "")
        out["merchant_no"] = df.get("merchant_no", "")
        out["status"] = df.get("status", "")
        out["category_or_type"] = df.get("category", df.get("trans_type", ""))
        out["remark"] = df.get("remark", "")
        return out

    details = pd.concat([norm(w, "wechat"), norm(a, "alipay")], ignore_index=True)
    details["debit_last4"] = details["pay_method"].map(_extract_debit_last4)
    details = details.dropna(subset=["debit_last4"])
    details["amount_abs"] = details["amount"].map(_to_decimal).map(lambda d: abs(d))
    details["trans_date_dt"] = details["trans_date"].map(lambda s: _to_date(s) or date.min)
    details["text"] = (details["counterparty"].fillna("") + " " + details["item"].fillna("")).str.strip()
    return details.reset_index(drop=True)


def _should_attempt_match(summary: str, counterparty: str) -> bool:
    s = summary.strip()
    c = counterparty.strip()
    keywords = ["快捷支付", "银联快捷支付", "快捷退款", "银联快捷退款", "支付宝", "财付通", "微信"]
    return any(k in s for k in keywords) or any(k in c for k in ["支付宝", "财付通", "微信"])


def match_bank_statements(
    bank_csvs: list[Path],
    wechat_csv: Path,
    alipay_csv: Path,
    out_dir: Path,
    max_day_diff: int = 1,
) -> None:
    details = _build_detail_df(wechat_csv, alipay_csv)
    used_detail_idx: set[int] = set()

    enriched_rows: list[dict[str, Any]] = []
    unmatched_rows: list[dict[str, Any]] = []
    observed_raw_cols: set[str] = set()

    for bank_csv in bank_csvs:
        df = pd.read_csv(bank_csv, dtype=str)
        raw_cols = list(df.columns)
        observed_raw_cols.update(raw_cols)
        df["trans_date_dt"] = df["trans_date"].map(lambda s: _to_date(s) or date.min)
        df["amount_dec"] = df["amount"].map(_to_decimal)
        df["amount_abs"] = df["amount_dec"].map(lambda d: abs(d))

        for _, row in df.iterrows():
            base = {col: row.get(col, "") for col in raw_cols}
            account_last4 = str(row.get("account_last4") or "").strip()
            summary = str(row.get("summary") or "").strip()
            counterparty = str(row.get("counterparty") or "").strip()

            if not account_last4:
                unmatched_rows.append({**base, "match_status": "missing_account_last4"})
                continue

            if not _should_attempt_match(summary, counterparty):
                unmatched_rows.append({**base, "match_status": "skipped_non_payment"})
                continue

            amount_abs: Decimal = row["amount_abs"]
            base_date: date = row["trans_date_dt"]
            date_set = {base_date + timedelta(days=d) for d in range(-max_day_diff, max_day_diff + 1)}

            candidates = details[
                (details["debit_last4"] == account_last4)
                & (details["amount_abs"] == amount_abs)
                & (details["trans_date_dt"].isin(date_set))
            ]

            if candidates.empty:
                unmatched_rows.append({**base, "match_status": "no_candidate"})
                continue

            is_refund = ("退款" in summary) or (row["amount_dec"] > 0 and summary.endswith("退款"))
            bank_text = f"{summary} {counterparty}".strip()

            best_idx: int | None = None
            best_score: tuple[int, int, int] | None = None
            for cand_idx, cand_row in candidates.iterrows():
                if cand_idx in used_detail_idx:
                    continue
                date_diff = abs((cand_row["trans_date_dt"] - base_date).days)
                dir_penalty = _direction_penalty(is_refund=is_refund, bank_amount=row["amount_dec"], detail_row=cand_row)
                sim = fuzz.partial_ratio(bank_text, cand_row.get("text", "") or "")
                score = (date_diff, dir_penalty, -sim)
                if best_score is None or score < best_score:
                    best_score = score
                    best_idx = int(cand_idx)

            if best_idx is None:
                unmatched_rows.append({**base, "match_status": "all_candidates_used"})
                continue

            used_detail_idx.add(best_idx)
            chosen = details.loc[best_idx]

            out = dict(base)
            out.update(
                {
                    "match_status": "matched",
                    "match_sources": f"cmb_statement({account_last4})+{chosen['channel']}",
                    "detail_channel": chosen["channel"],
                    "detail_trans_time": chosen["trans_time"],
                    "detail_trans_date": chosen["trans_date"],
                    "detail_direction": chosen["direction"],
                    "detail_counterparty": chosen["counterparty"],
                    "detail_item": chosen["item"],
                    "detail_pay_method": chosen["pay_method"],
                    "detail_trade_no": chosen["trade_no"],
                    "detail_merchant_no": chosen["merchant_no"],
                    "detail_status": chosen["status"],
                    "detail_category_or_type": chosen["category_or_type"],
                    "detail_remark": chosen["remark"],
                    "match_date_diff_days": best_score[0] if best_score else "",
                    "match_direction_penalty": best_score[1] if best_score else "",
                    "match_text_similarity": (-best_score[2]) if best_score else "",
                }
            )
            enriched_rows.append(out)

    out_dir.mkdir(parents=True, exist_ok=True)
    enriched_path = out_dir / "bank.enriched.csv"
    unmatched_path = out_dir / "bank.unmatched.csv"
    base_cols_preferred = [
        "source",
        "account_last4",
        "trans_date",
        "currency",
        "amount",
        "balance",
        "summary",
        "counterparty",
    ]
    extra_base_cols = sorted([c for c in observed_raw_cols if c not in base_cols_preferred])
    base_cols = base_cols_preferred + extra_base_cols

    enriched_cols = base_cols + [
        "match_status",
        "match_sources",
        "detail_channel",
        "detail_trans_time",
        "detail_trans_date",
        "detail_direction",
        "detail_counterparty",
        "detail_item",
        "detail_pay_method",
        "detail_trade_no",
        "detail_merchant_no",
        "detail_status",
        "detail_category_or_type",
        "detail_remark",
        "match_date_diff_days",
        "match_direction_penalty",
        "match_text_similarity",
    ]
    unmatched_cols = base_cols + ["match_status"]

    enriched_df = pd.DataFrame(enriched_rows, columns=enriched_cols)
    unmatched_df = pd.DataFrame(unmatched_rows, columns=unmatched_cols)
    enriched_df.to_csv(enriched_path, index=False, encoding="utf-8")
    unmatched_df.to_csv(unmatched_path, index=False, encoding="utf-8")

    xlsx_path = out_dir / "bank.match.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        enriched_df.to_excel(writer, index=False, sheet_name="enriched")
        unmatched_df.to_excel(writer, index=False, sheet_name="unmatched")

    print(f"[bank match] enriched={len(enriched_df)} -> {enriched_path}")
    print(f"[bank match] unmatched={len(unmatched_df)} -> {unmatched_path}")
    print(f"[bank match] xlsx -> {xlsx_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Match CMB debit statement txns with WeChat/Alipay details.")
    parser.add_argument("--wechat", type=Path, default=Path("output/wechat.normalized.csv"))
    parser.add_argument("--alipay", type=Path, default=Path("output/alipay.normalized.csv"))
    parser.add_argument("--out-dir", type=Path, default=Path("output"))
    parser.add_argument("--max-day-diff", type=int, default=1)
    parser.add_argument("bank_csv", type=Path, nargs="*")
    args = parser.parse_args()

    bank_csvs = list(args.bank_csv)
    if not bank_csvs:
        bank_csvs = sorted(Path("output").glob("招商银行交易流水*.transactions.csv"))
    if not bank_csvs:
        raise SystemExit("Cannot find bank statement CSV under output/; run extract_pdf_transactions.py first.")

    match_bank_statements(
        bank_csvs=bank_csvs,
        wechat_csv=args.wechat,
        alipay_csv=args.alipay,
        out_dir=args.out_dir,
        max_day_diff=args.max_day_diff,
    )


if __name__ == "__main__":
    main()
