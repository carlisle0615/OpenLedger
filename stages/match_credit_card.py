"""match_credit_card：将信用卡账单行与微信/支付宝明细进行匹配回填。

输入：
- `stages.extract_pdf` 产出的信用卡账单 CSV
- `stages.extract_exports` 产出的微信/支付宝标准化 CSV

输出：
- `<out-dir>/credit_card.enriched.csv`
- `<out-dir>/credit_card.unmatched.csv`
- `<out-dir>/credit_card.match.xlsx`

示例：
- `uv run python -m stages.match_credit_card --out-dir output`
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from rapidfuzz import fuzz

from ._common import log, make_parser


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


CARD_LAST4_RE = re.compile(r"信用卡\((\d{4})\)")


def _extract_last4(pay_method: Any) -> str | None:
    m = CARD_LAST4_RE.search(str(pay_method))
    return m.group(1) if m else None


def _candidate_channels(desc: str) -> list[Literal["wechat", "alipay"]]:
    if "财付通" in desc or "微信" in desc:
        return ["wechat"]
    if "支付宝" in desc:
        return ["alipay"]
    # 部分条目（例如“美团支付/京东支付”）也可能实际走微信/支付宝。
    return ["wechat", "alipay"]


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
        # 额外字段（便于人工核对/审计）。
        out["category_or_type"] = df.get("category", df.get("trans_type", ""))
        out["remark"] = df.get("remark", "")
        return out

    details = pd.concat([norm(w, "wechat"), norm(a, "alipay")], ignore_index=True)
    details["card_last4"] = details["pay_method"].map(_extract_last4)
    details = details.dropna(subset=["card_last4"])
    details["amount_dec"] = details["amount"].map(_to_decimal).map(lambda d: abs(d))
    details["trans_date_dt"] = details["trans_date"].map(lambda s: _to_date(s) or date.min)
    return details.reset_index(drop=True)


def _is_refund_detail(cand_row: pd.Series) -> bool:
    direction = str(cand_row.get("direction", "")).strip()
    status = str(cand_row.get("status", "")).strip()
    item = str(cand_row.get("item", "")).strip()
    category_or_type = str(cand_row.get("category_or_type", "")).strip()
    if "退款" in status or "退款" in item or "退款" in category_or_type:
        return True
    if direction in {"收入", "不计收支"}:
        return True
    return False


def _direction_penalty(section: str, cand_row: pd.Series) -> int:
    direction = str(cand_row.get("direction", "")).strip()
    if section == "消费":
        return 0 if direction == "支出" else 2
    if section == "退款":
        return 0 if _is_refund_detail(cand_row) else 2
    return 1


def _candidate_score(cc_desc: str, cc_section: str, cc_base_date: date, cand_row: pd.Series) -> tuple[int, int, int]:
    d = cand_row["trans_date_dt"]
    date_diff = abs((d - cc_base_date).days)
    dir_penalty = _direction_penalty(cc_section, cand_row)
    text = f"{cand_row.get('counterparty','')} {cand_row.get('item','')}".strip()
    sim = fuzz.partial_ratio(cc_desc, text) if text else 0
    # 越小越好：优先日期更近，其次方向符合，最后文本相似度更高。
    return (date_diff, dir_penalty, -sim)


def match_credit_card(
    credit_card_csv: Path,
    wechat_csv: Path,
    alipay_csv: Path,
    out_dir: Path,
    max_day_diff: int = 1,
) -> None:
    cc = pd.read_csv(credit_card_csv, dtype=str)
    required_cols = {"section", "trans_date", "post_date", "description", "amount_rmb", "card_last4"}
    missing = sorted(required_cols - set(cc.columns))
    if missing:
        bank_statement_cols = {
            "account_last4",
            "trans_date",
            "currency",
            "amount",
            "balance",
            "summary",
            "counterparty",
        }
        is_bank_statement = bank_statement_cols.issubset(set(cc.columns))
        hint = ""
        if is_bank_statement:
            hint = (
                "你传入的看起来是 *银行交易流水* CSV（例如：招商银行交易流水*.transactions.csv）。"
                "请改用 `python -m stages.match_bank` 处理。"
            )
        else:
            hint = "请确认传入的是 *信用卡账单* CSV（例如：*信用卡账单*.transactions.csv）。"
        raise SystemExit(
            "--credit-card CSV 表结构不符合预期。\n"
            f"- 文件: {credit_card_csv}\n"
            f"- 缺少列: {missing}\n"
            f"- 实际列: {list(cc.columns)}\n"
            f"- 提示: {hint}\n"
        )
    cc_raw_cols = list(cc.columns)
    cc["trans_date_dt"] = cc["trans_date"].map(lambda s: _to_date(s) or date.min)
    cc["post_date_dt"] = cc["post_date"].map(_to_date)
    cc["amount_dec"] = cc["amount_rmb"].map(_to_decimal)
    cc["amount_abs"] = cc["amount_dec"].map(lambda d: abs(d))

    details = _build_detail_df(wechat_csv, alipay_csv)

    used_detail_idx: set[int] = set()
    match_rows: list[dict[str, Any]] = []
    unmatched_rows: list[dict[str, Any]] = []

    for _, row in cc.iterrows():
        base = {col: row.get(col, "") for col in cc_raw_cols}
        section = (row.get("section") or "").strip()
        if section not in {"消费", "退款"}:
            unmatched_rows.append({**base, "match_status": "skipped_section"})
            continue

        desc = (row.get("description") or "").strip()
        last4 = (row.get("card_last4") or "").strip()
        if not last4:
            unmatched_rows.append({**base, "match_status": "missing_last4"})
            continue

        channels = _candidate_channels(desc)

        amount_abs: Decimal = row["amount_abs"]
        base_dates: list[date] = [row["trans_date_dt"]]
        if row["post_date_dt"]:
            base_dates.append(row["post_date_dt"])

        candidates = pd.DataFrame()
        for base_date in base_dates:
            date_set = {base_date + timedelta(days=d) for d in range(-max_day_diff, max_day_diff + 1)}
            cand = details[
                (details["channel"].isin(channels))
                & (details["card_last4"] == last4)
                & (details["amount_dec"] == amount_abs)
                & (details["trans_date_dt"].isin(date_set))
            ]
            if not cand.empty:
                candidates = cand
                base_date_for_score = base_date
                break

        if candidates.empty:
            unmatched_rows.append(
                {
                    **base,
                    "match_status": "no_candidate",
                    "match_channels_tried": "+".join(channels),
                }
            )
            continue

        best_idx: int | None = None
        best_score: tuple[int, int, int] | None = None
        for cand_idx, cand_row in candidates.iterrows():
            if cand_idx in used_detail_idx:
                continue
            score = _candidate_score(desc, section, base_date_for_score, cand_row)
            if best_score is None or score < best_score:
                best_score = score
                best_idx = int(cand_idx)

        if best_idx is None:
            unmatched_rows.append({**base, "match_status": "all_candidates_used"})
            continue

        used_detail_idx.add(best_idx)
        chosen = details.loc[best_idx]
        out = dict(base)
        src = str(base.get("source") or "").strip() or "credit_card"
        out.update(
            {
                "match_status": "matched",
                "match_sources": f"{src}+{chosen['channel']}",
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
        match_rows.append(out)

    out_dir.mkdir(parents=True, exist_ok=True)
    matched_path = out_dir / "credit_card.enriched.csv"
    unmatched_path = out_dir / "credit_card.unmatched.csv"
    matched_cols = cc_raw_cols + [
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
    unmatched_cols = cc_raw_cols + ["match_status", "match_channels_tried"]
    matched_df = pd.DataFrame(match_rows, columns=matched_cols)
    unmatched_df = pd.DataFrame(unmatched_rows, columns=unmatched_cols)
    matched_df.to_csv(matched_path, index=False, encoding="utf-8")
    unmatched_df.to_csv(unmatched_path, index=False, encoding="utf-8")

    xlsx_path = out_dir / "credit_card.match.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        matched_df.to_excel(writer, index=False, sheet_name="enriched")
        unmatched_df.to_excel(writer, index=False, sheet_name="unmatched")

    log("match_credit_card", f"已匹配={len(match_rows)} 输出={matched_path}")
    log("match_credit_card", f"未匹配={len(unmatched_rows)} 输出={unmatched_path}")
    log("match_credit_card", f"Excel={xlsx_path}")


def main() -> None:
    parser = make_parser("将信用卡账单与微信/支付宝明细进行匹配回填。")
    parser.add_argument("--credit-card", type=Path, default=None)
    parser.add_argument("--wechat", type=Path, default=Path("output/wechat.normalized.csv"))
    parser.add_argument("--alipay", type=Path, default=Path("output/alipay.normalized.csv"))
    parser.add_argument("--out-dir", type=Path, default=Path("output"), help="输出目录。")
    parser.add_argument("--max-day-diff", type=int, default=1)
    args = parser.parse_args()

    if args.credit_card is None:
        import csv

        required_cols = {"section", "trans_date", "post_date", "description", "amount_rmb", "card_last4"}
        candidates = sorted(Path("output").glob("*.transactions.csv"))
        matches: list[Path] = []
        for p in candidates:
            try:
                with p.open("r", encoding="utf-8", errors="replace", newline="") as f:
                    header = next(csv.reader(f), [])
                cols = {str(x).strip() for x in header if str(x).strip()}
            except Exception:
                continue
            if required_cols.issubset(cols):
                matches.append(p)
        if not matches:
            matches = sorted(Path("output").glob("*信用卡*.transactions.csv"))
        if not matches:
            raise SystemExit(
                "在 output/ 下找不到可用的信用卡账单 CSV；请先运行 `python -m stages.extract_pdf`，"
                "或手动用 --credit-card 指定信用卡类型的 *.transactions.csv。"
            )
        args.credit_card = matches[0]

    match_credit_card(
        credit_card_csv=args.credit_card,
        wechat_csv=args.wechat,
        alipay_csv=args.alipay,
        out_dir=args.out_dir,
        max_day_diff=args.max_day_diff,
    )


if __name__ == "__main__":
    main()
