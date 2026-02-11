"""match_bank：将借记卡流水与微信/支付宝明细进行匹配回填。

输入：
- `stages.extract_pdf` 产出的一个或多个银行流水 CSV
- `stages.extract_exports` 产出的微信/支付宝标准化 CSV

输出：
- `<out-dir>/bank.enriched.csv`
- `<out-dir>/bank.unmatched.csv`
- `<out-dir>/bank.match.xlsx`
- `<out-dir>/bank.match_debug.csv`

示例：
- `uv run python -m stages.match_bank --out-dir output`
"""

from __future__ import annotations

import itertools
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from rapidfuzz import fuzz

from ._common import log, make_parser

MATCH_DEBUG_COLUMNS = [
    "row_index",
    "account_last4",
    "trans_date",
    "amount",
    "summary",
    "counterparty",
    "candidate_count_exact",
    "candidate_count_sum",
    "best_date_diff_days",
    "best_direction_penalty",
    "best_text_similarity",
    "match_method",
    "match_status",
    "match_confidence",
    "chosen_count",
    "chosen_channels",
]


def _to_decimal(value: Any) -> Decimal:
    s = str(value).strip()
    s = s.replace("¥", "").replace("￥", "").replace(",", "").strip()
    if s in {"", "nan", "NaN", "None"}:
        raise ValueError(f"金额为空: {value!r}")
    try:
        return Decimal(s)
    except InvalidOperation as exc:  # pragma: no cover - 防御性分支
        raise ValueError(f"无效的金额: {value!r}") from exc


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


def _calc_confidence(date_diff: int, dir_penalty: int, sim: int, max_day_diff: int, parts: int = 1) -> float:
    day_span = max(1, max_day_diff + 1)
    date_score = max(0.0, 1.0 - (date_diff / day_span))
    dir_score = 1.0 if dir_penalty <= 0 else max(0.0, 1.0 - 0.35 * dir_penalty)
    text_score = max(0.0, min(sim, 100) / 100)
    base = 0.45 * date_score + 0.35 * text_score + 0.2 * dir_score
    if parts > 1:
        base *= max(0.55, 1.0 - 0.12 * (parts - 1))
    return round(min(max(base, 0.0), 1.0), 3)


def _join_detail_values(values: list[Any]) -> str:
    out: list[str] = []
    seen = set()
    for v in values:
        s = str(v or "").strip()
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return " | ".join(out)


def _best_sum_match(
    candidates: pd.DataFrame,
    used_detail_idx: set[int],
    amount_abs: Decimal,
    bank_text: str,
    is_refund: bool,
    bank_amount: Decimal,
    base_date: date,
    max_day_diff: int,
    max_parts: int = 3,
) -> tuple[list[pd.Series], tuple[int, int, int]] | None:
    available = candidates[~candidates.index.isin(used_detail_idx)]
    if available.empty:
        return None
    rows = list(available.iterrows())
    if len(rows) > 30:
        return None

    best_combo: list[pd.Series] | None = None
    best_score: tuple[int, int, int] | None = None
    for k in range(2, max_parts + 1):
        for combo in itertools.combinations(rows, k):
            total = sum((row["amount_abs"] for _, row in combo), Decimal(0))
            if total != amount_abs:
                continue
            date_diff = min(abs((row["trans_date_dt"] - base_date).days) for _, row in combo)
            dir_penalty = max(
                _direction_penalty(is_refund=is_refund, bank_amount=bank_amount, detail_row=row)
                for _, row in combo
            )
            text = " ".join((row.get("text", "") or "") for _, row in combo).strip()
            sim = fuzz.partial_ratio(bank_text, text) if text else 0
            score = (date_diff, dir_penalty, -sim)
            if best_score is None or score < best_score:
                best_score = score
                best_combo = [row for _, row in combo]
    if best_combo is None or best_score is None:
        return None
    for row in best_combo:
        if int(row.name) in used_detail_idx:
            return None
    return best_combo, best_score


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
    debug_rows: list[dict[str, Any]] = []
    observed_raw_cols: set[str] = set()

    for bank_csv in bank_csvs:
        df = pd.read_csv(bank_csv, dtype=str)
        raw_cols = list(df.columns)
        observed_raw_cols.update(raw_cols)
        df["trans_date_dt"] = df["trans_date"].map(lambda s: _to_date(s) or date.min)
        df["amount_dec"] = df["amount"].map(_to_decimal)
        df["amount_abs"] = df["amount_dec"].map(lambda d: abs(d))

        for row_index, row in df.iterrows():
            base = {col: row.get(col, "") for col in raw_cols}
            account_last4 = str(row.get("account_last4") or "").strip()
            summary = str(row.get("summary") or "").strip()
            counterparty = str(row.get("counterparty") or "").strip()
            debug: dict[str, Any] = {
                "row_index": row_index,
                "account_last4": account_last4,
                "trans_date": row.get("trans_date", ""),
                "amount": row.get("amount", ""),
                "summary": summary,
                "counterparty": counterparty,
                "candidate_count_exact": 0,
                "candidate_count_sum": 0,
                "best_date_diff_days": "",
                "best_direction_penalty": "",
                "best_text_similarity": "",
                "match_method": "",
                "match_status": "",
                "match_confidence": "",
                "chosen_count": 0,
                "chosen_channels": "",
            }

            if not account_last4:
                unmatched_rows.append({**base, "match_status": "missing_account_last4"})
                debug["match_status"] = "missing_account_last4"
                debug_rows.append(debug)
                continue

            if not _should_attempt_match(summary, counterparty):
                unmatched_rows.append({**base, "match_status": "skipped_non_payment"})
                debug["match_status"] = "skipped_non_payment"
                debug_rows.append(debug)
                continue

            amount_abs: Decimal = row["amount_abs"]
            base_date: date = row["trans_date_dt"]
            date_set = {base_date + timedelta(days=d) for d in range(-max_day_diff, max_day_diff + 1)}

            candidates = details[
                (details["debit_last4"] == account_last4)
                & (details["amount_abs"] == amount_abs)
                & (details["trans_date_dt"].isin(date_set))
            ]
            candidates_sum = details[
                (details["debit_last4"] == account_last4)
                & (details["amount_abs"] <= amount_abs)
                & (details["trans_date_dt"].isin(date_set))
            ]

            debug["candidate_count_exact"] = int(len(candidates))
            debug["candidate_count_sum"] = int(len(candidates_sum))

            if candidates.empty and candidates_sum.empty:
                unmatched_rows.append({**base, "match_status": "no_candidate"})
                debug["match_status"] = "no_candidate"
                debug_rows.append(debug)
                continue

            is_refund = ("退款" in summary) or (row["amount_dec"] > 0 and summary.endswith("退款"))
            bank_text = f"{summary} {counterparty}".strip()

            best_idx: int | None = None
            best_score: tuple[int, int, int] | None = None
            match_method = ""
            chosen_rows: list[pd.Series] | None = None

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

            if best_idx is not None:
                used_detail_idx.add(best_idx)
                chosen_rows = [details.loc[best_idx]]
                match_method = "exact"
            else:
                sum_hit = _best_sum_match(
                    candidates_sum,
                    used_detail_idx,
                    amount_abs=amount_abs,
                    bank_text=bank_text,
                    is_refund=is_refund,
                    bank_amount=row["amount_dec"],
                    base_date=base_date,
                    max_day_diff=max_day_diff,
                )
                if sum_hit:
                    chosen_rows, best_score = sum_hit
                    for r in chosen_rows:
                        used_detail_idx.add(int(r.name))
                    match_method = f"sum_{len(chosen_rows)}"

            if not chosen_rows:
                unmatched_rows.append({**base, "match_status": "all_candidates_used"})
                debug["match_status"] = "all_candidates_used"
                debug_rows.append(debug)
                continue

            src = str(base.get("source") or "").strip() or "bank_statement"
            channels_used = sorted({str(r.get("channel") or "") for r in chosen_rows if str(r.get("channel") or "")})
            match_sources = f"{src}({account_last4})+{channels_used[0]}"
            if len(channels_used) > 1:
                match_sources = f"{src}({account_last4})+{'+'.join(channels_used)}"
            elif match_method.startswith("sum_"):
                match_sources = f"{src}({account_last4})+{channels_used[0]}*{len(chosen_rows)}"

            sim = (-best_score[2]) if best_score else 0
            confidence = _calc_confidence(
                date_diff=best_score[0] if best_score else 0,
                dir_penalty=best_score[1] if best_score else 0,
                sim=sim,
                max_day_diff=max_day_diff,
                parts=len(chosen_rows),
            )

            out = dict(base)
            out.update(
                {
                    "match_status": "matched",
                    "match_method": match_method,
                    "match_sources": match_sources,
                    "detail_channel": _join_detail_values([r.get("channel") for r in chosen_rows]),
                    "detail_trans_time": _join_detail_values([r.get("trans_time") for r in chosen_rows]),
                    "detail_trans_date": _join_detail_values([r.get("trans_date") for r in chosen_rows]),
                    "detail_direction": _join_detail_values([r.get("direction") for r in chosen_rows]),
                    "detail_counterparty": _join_detail_values([r.get("counterparty") for r in chosen_rows]),
                    "detail_item": _join_detail_values([r.get("item") for r in chosen_rows]),
                    "detail_pay_method": _join_detail_values([r.get("pay_method") for r in chosen_rows]),
                    "detail_trade_no": _join_detail_values([r.get("trade_no") for r in chosen_rows]),
                    "detail_merchant_no": _join_detail_values([r.get("merchant_no") for r in chosen_rows]),
                    "detail_status": _join_detail_values([r.get("status") for r in chosen_rows]),
                    "detail_category_or_type": _join_detail_values([r.get("category_or_type") for r in chosen_rows]),
                    "detail_remark": _join_detail_values([r.get("remark") for r in chosen_rows]),
                    "match_date_diff_days": best_score[0] if best_score else "",
                    "match_direction_penalty": best_score[1] if best_score else "",
                    "match_text_similarity": sim if best_score else "",
                    "match_confidence": confidence,
                }
            )
            enriched_rows.append(out)

            debug.update(
                {
                    "match_status": "matched",
                    "match_method": match_method,
                    "best_date_diff_days": best_score[0] if best_score else "",
                    "best_direction_penalty": best_score[1] if best_score else "",
                    "best_text_similarity": sim if best_score else "",
                    "match_confidence": confidence,
                    "chosen_count": len(chosen_rows),
                    "chosen_channels": _join_detail_values([r.get("channel") for r in chosen_rows]),
                }
            )
            debug_rows.append(debug)

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
        "match_method",
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
        "match_confidence",
    ]
    unmatched_cols = base_cols + ["match_status", "match_method", "match_confidence"]

    enriched_df = pd.DataFrame(enriched_rows, columns=enriched_cols)
    unmatched_df = pd.DataFrame(unmatched_rows, columns=unmatched_cols)
    enriched_df.to_csv(enriched_path, index=False, encoding="utf-8")
    unmatched_df.to_csv(unmatched_path, index=False, encoding="utf-8")

    xlsx_path = out_dir / "bank.match.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        enriched_df.to_excel(writer, index=False, sheet_name="enriched")
        unmatched_df.to_excel(writer, index=False, sheet_name="unmatched")

    debug_path = out_dir / "bank.match_debug.csv"
    debug_df = pd.DataFrame(debug_rows, columns=MATCH_DEBUG_COLUMNS)
    debug_df.to_csv(debug_path, index=False, encoding="utf-8")

    log("match_bank", f"已匹配={len(enriched_df)} 输出={enriched_path}")
    log("match_bank", f"未匹配={len(unmatched_df)} 输出={unmatched_path}")
    log("match_bank", f"Excel={xlsx_path}")
    log("match_bank", f"Debug={debug_path}")


def main() -> None:
    parser = make_parser("将借记卡流水与微信/支付宝明细进行匹配回填。")
    parser.add_argument("--wechat", type=Path, default=Path("output/wechat.normalized.csv"))
    parser.add_argument("--alipay", type=Path, default=Path("output/alipay.normalized.csv"))
    parser.add_argument("--out-dir", type=Path, default=Path("output"), help="输出目录。")
    parser.add_argument("--max-day-diff", type=int, default=1)
    parser.add_argument("bank_csv", type=Path, nargs="*")
    args = parser.parse_args()

    bank_csvs = list(args.bank_csv)
    if not bank_csvs:
        import csv

        required_cols = {
            "account_last4",
            "trans_date",
            "currency",
            "amount",
            "balance",
            "summary",
            "counterparty",
        }
        candidates = sorted(Path("output").glob("*.transactions.csv"))
        for p in candidates:
            try:
                with p.open("r", encoding="utf-8", errors="replace", newline="") as f:
                    header = next(csv.reader(f), [])
                cols = {str(x).strip() for x in header if str(x).strip()}
            except Exception:
                continue
            if required_cols.issubset(cols):
                bank_csvs.append(p)
        if not bank_csvs:
            bank_csvs = sorted(Path("output").glob("*交易流水*.transactions.csv"))
    if not bank_csvs:
        raise SystemExit(
            "在 output/ 下找不到可用的借记卡流水 CSV；请先运行 `python -m stages.extract_pdf`，"
            "或手动把 bank 类型的 *.transactions.csv 作为参数传入。"
        )

    match_bank_statements(
        bank_csvs=bank_csvs,
        wechat_csv=args.wechat,
        alipay_csv=args.alipay,
        out_dir=args.out_dir,
        max_day_diff=args.max_day_diff,
    )


if __name__ == "__main__":
    main()
