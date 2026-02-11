"""match_credit_card：将信用卡账单行与微信/支付宝明细进行匹配回填。

输入：
- `stages.extract_pdf` 产出的信用卡账单 CSV
- `stages.extract_exports` 产出的微信/支付宝标准化 CSV

输出：
- `<out-dir>/credit_card.enriched.csv`
- `<out-dir>/credit_card.unmatched.csv`
- `<out-dir>/credit_card.match.xlsx`
- `<out-dir>/credit_card.match_debug.csv`

示例：
- `uv run python -m stages.match_credit_card --out-dir output`
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
    "section",
    "trans_date",
    "post_date",
    "amount_rmb",
    "card_last4",
    "description",
    "channels_tried",
    "base_date",
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
    cc_desc: str,
    cc_section: str,
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
    best_combo_idx: list[int] | None = None
    best_score: tuple[int, int, int] | None = None
    for k in range(2, max_parts + 1):
        for combo in itertools.combinations(rows, k):
            total = sum((row["amount_dec"] for _, row in combo), Decimal(0))
            if total != amount_abs:
                continue
            date_diff = min(abs((row["trans_date_dt"] - base_date).days) for _, row in combo)
            dir_penalty = max(_direction_penalty(cc_section, row) for _, row in combo)
            text = " ".join(
                f"{row.get('counterparty','')} {row.get('item','')}".strip() for _, row in combo
            ).strip()
            sim = fuzz.partial_ratio(cc_desc, text) if text else 0
            score = (date_diff, dir_penalty, -sim)
            if best_score is None or score < best_score:
                best_score = score
                best_combo = [row for _, row in combo]
                best_combo_idx = [int(idx) for idx, _ in combo]
    if best_combo is None or best_score is None:
        return None
    for idx in best_combo_idx or []:
        if idx in used_detail_idx:
            return None
    return best_combo, best_score


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
    debug_rows: list[dict[str, Any]] = []

    for row_index, row in cc.iterrows():
        base = {col: row.get(col, "") for col in cc_raw_cols}
        section = (row.get("section") or "").strip()
        debug: dict[str, Any] = {
            "row_index": row_index,
            "section": section,
            "trans_date": row.get("trans_date", ""),
            "post_date": row.get("post_date", ""),
            "amount_rmb": row.get("amount_rmb", ""),
            "card_last4": row.get("card_last4", ""),
            "description": row.get("description", ""),
            "channels_tried": "",
            "base_date": "",
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
        if section not in {"消费", "退款"}:
            unmatched_rows.append({**base, "match_status": "skipped_section"})
            debug["match_status"] = "skipped_section"
            debug_rows.append(debug)
            continue

        desc = (row.get("description") or "").strip()
        last4 = (row.get("card_last4") or "").strip()
        if not last4:
            unmatched_rows.append({**base, "match_status": "missing_last4"})
            debug["match_status"] = "missing_last4"
            debug_rows.append(debug)
            continue

        channels = _candidate_channels(desc)
        debug["channels_tried"] = "+".join(channels)

        amount_abs: Decimal = row["amount_abs"]
        base_dates: list[date] = [row["trans_date_dt"]]
        if row["post_date_dt"]:
            base_dates.append(row["post_date_dt"])

        candidates = pd.DataFrame()
        candidates_sum = pd.DataFrame()
        base_date_for_score: date | None = None
        for base_date in base_dates:
            date_set = {base_date + timedelta(days=d) for d in range(-max_day_diff, max_day_diff + 1)}
            cand = details[
                (details["channel"].isin(channels))
                & (details["card_last4"] == last4)
                & (details["amount_dec"] == amount_abs)
                & (details["trans_date_dt"].isin(date_set))
            ]
            cand_sum = details[
                (details["channel"].isin(channels))
                & (details["card_last4"] == last4)
                & (details["amount_dec"] <= amount_abs)
                & (details["trans_date_dt"].isin(date_set))
            ]
            if not cand.empty or not cand_sum.empty:
                candidates = cand
                candidates_sum = cand_sum
                base_date_for_score = base_date
                break

        debug["candidate_count_exact"] = int(len(candidates))
        debug["candidate_count_sum"] = int(len(candidates_sum))
        if base_date_for_score:
            debug["base_date"] = base_date_for_score.isoformat()

        if candidates.empty and candidates_sum.empty:
            unmatched_rows.append(
                {
                    **base,
                    "match_status": "no_candidate",
                    "match_channels_tried": "+".join(channels),
                }
            )
            debug["match_status"] = "no_candidate"
            debug_rows.append(debug)
            continue

        best_idx: int | None = None
        best_score: tuple[int, int, int] | None = None
        match_method = ""
        chosen_rows: list[pd.Series] | None = None

        for cand_idx, cand_row in candidates.iterrows():
            if cand_idx in used_detail_idx:
                continue
            score = _candidate_score(desc, section, base_date_for_score, cand_row)
            if best_score is None or score < best_score:
                best_score = score
                best_idx = int(cand_idx)

        if best_idx is not None:
            used_detail_idx.add(best_idx)
            chosen_rows = [details.loc[best_idx]]
            match_method = "exact"
        else:
            best_sum: tuple[list[pd.Series], tuple[int, int, int]] | None = None
            for ch in channels:
                ch_cands = candidates_sum[candidates_sum["channel"] == ch] if not candidates_sum.empty else candidates_sum
                hit = _best_sum_match(
                    ch_cands,
                    used_detail_idx,
                    amount_abs=amount_abs,
                    cc_desc=desc,
                    cc_section=section,
                    base_date=base_date_for_score,
                    max_day_diff=max_day_diff,
                )
                if hit:
                    best_sum = hit
                    break

            if best_sum:
                chosen_rows, best_score = best_sum
                for r in chosen_rows:
                    used_detail_idx.add(int(r.name))
                match_method = f"sum_{len(chosen_rows)}"

        if not chosen_rows:
            unmatched_rows.append({**base, "match_status": "all_candidates_used"})
            debug["match_status"] = "all_candidates_used"
            debug_rows.append(debug)
            continue

        src = str(base.get("source") or "").strip() or "credit_card"
        channels_used = sorted({str(r.get("channel") or "") for r in chosen_rows if str(r.get("channel") or "")})
        match_sources = f"{src}+{channels_used[0]}"
        if len(channels_used) > 1:
            match_sources = f"{src}+{'+'.join(channels_used)}"
        elif match_method.startswith("sum_"):
            match_sources = f"{src}+{channels_used[0]}*{len(chosen_rows)}"

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
        match_rows.append(out)

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
    matched_path = out_dir / "credit_card.enriched.csv"
    unmatched_path = out_dir / "credit_card.unmatched.csv"
    matched_cols = cc_raw_cols + [
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
    unmatched_cols = cc_raw_cols + ["match_status", "match_channels_tried", "match_method", "match_confidence"]
    matched_df = pd.DataFrame(match_rows, columns=matched_cols)
    unmatched_df = pd.DataFrame(unmatched_rows, columns=unmatched_cols)
    matched_df.to_csv(matched_path, index=False, encoding="utf-8")
    unmatched_df.to_csv(unmatched_path, index=False, encoding="utf-8")

    xlsx_path = out_dir / "credit_card.match.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        matched_df.to_excel(writer, index=False, sheet_name="enriched")
        unmatched_df.to_excel(writer, index=False, sheet_name="unmatched")

    debug_path = out_dir / "credit_card.match_debug.csv"
    debug_df = pd.DataFrame(debug_rows, columns=MATCH_DEBUG_COLUMNS)
    debug_df.to_csv(debug_path, index=False, encoding="utf-8")

    log("match_credit_card", f"已匹配={len(match_rows)} 输出={matched_path}")
    log("match_credit_card", f"未匹配={len(unmatched_rows)} 输出={unmatched_path}")
    log("match_credit_card", f"Excel={xlsx_path}")
    log("match_credit_card", f"Debug={debug_path}")


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
