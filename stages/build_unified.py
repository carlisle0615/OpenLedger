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
- `uv run python -m stages.build_unified --out-dir output`
"""

from __future__ import annotations

import calendar
import hashlib
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from openledger.stage_contracts import (
    ART_ALIPAY_NORMALIZED,
    ART_BANK_ENRICHED,
    ART_BANK_UNMATCHED,
    ART_CC_ENRICHED,
    ART_CC_UNMATCHED,
    ART_UNIFIED_TX,
    ART_WECHAT_NORMALIZED,
    required_columns,
)

from ._common import log, make_parser

CC_ENRICHED_COLUMNS = required_columns(ART_CC_ENRICHED)
CC_UNMATCHED_COLUMNS = required_columns(ART_CC_UNMATCHED)
BANK_ENRICHED_COLUMNS = required_columns(ART_BANK_ENRICHED)
BANK_UNMATCHED_COLUMNS = required_columns(ART_BANK_UNMATCHED)
WECHAT_NORMALIZED_COLUMNS = required_columns(ART_WECHAT_NORMALIZED)
ALIPAY_NORMALIZED_COLUMNS = required_columns(ART_ALIPAY_NORMALIZED)
UNIFIED_COLUMNS = required_columns(ART_UNIFIED_TX)


@dataclass(frozen=True, slots=True)
class Period:
    start_date: date
    end_date: date
    label: str


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


def _clean_str(value: Any) -> str:
    s = str(value or "").strip()
    return "" if s.lower() == "nan" else s


def _split_joined(value: Any) -> list[str]:
    s = _clean_str(value)
    if not s:
        return []
    return [v.strip() for v in s.split("|") if v.strip()]


def _dedup(values: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for v in values:
        s = _clean_str(v)
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _detail_descriptor(channel: str, row: pd.Series) -> str:
    channel = _clean_str(channel)
    trans_date = _clean_str(row.get("trans_date"))
    trans_time = _clean_str(row.get("trans_time"))
    amount = _clean_str(row.get("amount"))
    counterparty = _clean_str(row.get("counterparty"))
    item = _clean_str(row.get("item"))
    trade_no = _clean_str(row.get("trade_no"))
    merchant_no = _clean_str(row.get("merchant_no"))

    parts: list[str] = []
    if channel:
        parts.append(channel)
    if trans_date or trans_time:
        parts.append(f"{trans_date} {trans_time}".strip())
    if amount:
        parts.append(f"￥{amount}")
    if counterparty or item:
        parts.append(f"{counterparty} {item}".strip())

    id_parts: list[str] = []
    if trade_no:
        id_parts.append(f"trade_no={trade_no}")
    if merchant_no:
        id_parts.append(f"merchant_no={merchant_no}")
    if id_parts:
        parts.append("[" + ", ".join(id_parts) + "]")

    return " ".join([p for p in parts if p])


def _build_detail_lookup(wechat_norm: pd.DataFrame, alipay_norm: pd.DataFrame) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}

    def ingest(df: pd.DataFrame, channel: str) -> None:
        if df.empty:
            return
        df = _ensure_cols(
            df.copy(),
            [
                "trans_time",
                "trans_date",
                "amount",
                "counterparty",
                "item",
                "trade_no",
                "merchant_no",
            ],
        )
        for _, row in df.iterrows():
            desc = _detail_descriptor(channel, row)
            for key in [_clean_str(row.get("trade_no")), _clean_str(row.get("merchant_no"))]:
                if not key:
                    continue
                lookup.setdefault(key, []).append(desc)

    ingest(wechat_norm, "wechat")
    ingest(alipay_norm, "alipay")

    return {k: _dedup(v) for k, v in lookup.items()}


def _extract_detail_ids(row: pd.Series) -> list[str]:
    return _dedup(_split_joined(row.get("detail_trade_no")) + _split_joined(row.get("detail_merchant_no")))


def _fallback_detail_summary(row: pd.Series) -> str:
    channels = _split_joined(row.get("detail_channel"))
    times = _split_joined(row.get("detail_trans_time"))
    parties = _split_joined(row.get("detail_counterparty"))
    items = _split_joined(row.get("detail_item"))
    parts: list[str] = []
    if channels:
        parts.append("渠道=" + ", ".join(channels))
    if times:
        parts.append("时间=" + ", ".join(times))
    if parties:
        parts.append("对手方=" + ", ".join(parties))
    if items:
        parts.append("商品=" + ", ".join(items))
    return "；".join(parts)


def _detail_refs_for_row(row: pd.Series, detail_lookup: dict[str, list[str]]) -> list[str]:
    refs: list[str] = []
    for key in _extract_detail_ids(row):
        hits = detail_lookup.get(key)
        if hits:
            refs.extend(hits)
        else:
            refs.append(f"id={key}")
    refs = _dedup(refs)
    if refs:
        return refs
    fallback = _fallback_detail_summary(row)
    return [fallback] if fallback else []


def _join_refs(refs: list[str], limit: int = 6) -> str:
    refs = _dedup(refs)
    if not refs:
        return ""
    if len(refs) <= limit:
        return " | ".join(refs)
    return " | ".join(refs[:limit]) + f" 等{len(refs)}条"


def _hash_group_id(seed: str) -> str:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"mg_{digest}"


def _match_group_id_from_detail_ids(detail_ids: list[str]) -> str:
    ids = sorted(_dedup(detail_ids))
    if not ids:
        return ""
    return _hash_group_id("|".join(ids))


def _match_group_id_from_bill(seed: str) -> str:
    seed = _clean_str(seed)
    if not seed:
        return ""
    return _hash_group_id(f"bill|{seed}")


def _detail_group_id(row: pd.Series, detail_to_group_map: dict[str, str]) -> str:
    if not detail_to_group_map:
        return ""
    ids = _dedup([_clean_str(row.get("trade_no")), _clean_str(row.get("merchant_no"))])
    if not ids:
        return ""
    groups = _dedup([detail_to_group_map.get(k, "") for k in ids])
    groups = [g for g in groups if g]
    if not groups:
        return ""
    return sorted(groups)[0]


def _detail_match_remark(row: pd.Series, detail_to_bill_map: dict[str, list[str]]) -> str:
    if not detail_to_bill_map:
        return ""
    ids = _dedup([_clean_str(row.get("trade_no")), _clean_str(row.get("merchant_no"))])
    if not ids:
        return ""
    bills = _dedup(sum([detail_to_bill_map.get(k, []) for k in ids], []))
    if not bills:
        return ""
    return f"匹配到账单：{_join_refs(bills)}"


def _cc_account(source: Any, card_last4: Any) -> str:
    src = _clean_str(source)
    last4 = _clean_str(card_last4) or "?"
    if src.endswith("_credit_card"):
        bank_id = src.split("_", 1)[0].upper()
        return f"{bank_id} CreditCard({last4})"
    return f"{src}({last4})" if src else f"CreditCard({last4})"


def _bank_account(source: Any, account_last4: Any) -> str:
    src = _clean_str(source)
    last4 = _clean_str(account_last4) or "?"
    if src.endswith("_statement"):
        bank_id = src.split("_", 1)[0].upper()
        return f"{bank_id} Debit({last4})"
    return f"{src}({last4})" if src else f"Debit({last4})"


def _bill_descriptor_cc(row: pd.Series) -> str:
    account = _cc_account(row.get("source"), row.get("card_last4"))
    trans_date = _clean_str(row.get("trans_date"))
    amount = _clean_str(row.get("amount_rmb"))
    desc = _clean_str(row.get("description"))
    parts = [p for p in [account, trans_date, amount, desc] if p]
    return " ".join(parts)


def _bill_descriptor_bank(row: pd.Series) -> str:
    account = _bank_account(row.get("source"), row.get("account_last4"))
    trans_date = _clean_str(row.get("trans_date"))
    amount = _clean_str(row.get("amount"))
    summary = _clean_str(row.get("summary"))
    counterparty = _clean_str(row.get("counterparty"))
    tail = summary or counterparty
    parts = [p for p in [account, trans_date, amount, tail] if p]
    return " ".join(parts)


def _build_detail_to_bill_map(
    cc_enriched: pd.DataFrame, bank_enriched: pd.DataFrame
) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}

    def ingest(df: pd.DataFrame, bill_fn) -> None:
        if df.empty:
            return
        df = _ensure_cols(
            df.copy(),
            [
                "match_status",
                "detail_trade_no",
                "detail_merchant_no",
            ],
        )
        for _, row in df.iterrows():
            if _clean_str(row.get("match_status")) != "matched":
                continue
            ids = _extract_detail_ids(row)
            if not ids:
                continue
            bill = bill_fn(row)
            for key in ids:
                mapping.setdefault(key, []).append(bill)

    ingest(cc_enriched, _bill_descriptor_cc)
    ingest(bank_enriched, _bill_descriptor_bank)

    return {k: _dedup(v) for k, v in mapping.items()}


def _build_detail_to_group_map(
    cc_enriched: pd.DataFrame, bank_enriched: pd.DataFrame
) -> dict[str, str]:
    mapping: dict[str, str] = {}

    def ingest(df: pd.DataFrame, bill_fn) -> None:
        if df.empty:
            return
        df = _ensure_cols(
            df.copy(),
            [
                "match_status",
                "detail_trade_no",
                "detail_merchant_no",
            ],
        )
        for _, row in df.iterrows():
            if _clean_str(row.get("match_status")) != "matched":
                continue
            ids = _extract_detail_ids(row)
            if not ids:
                continue
            group_id = _match_group_id_from_detail_ids(ids)
            if not group_id:
                group_id = _match_group_id_from_bill(bill_fn(row))
            if not group_id:
                continue
            for key in ids:
                if key in mapping:
                    continue
                mapping[key] = group_id

    ingest(cc_enriched, _bill_descriptor_cc)
    ingest(bank_enriched, _bill_descriptor_bank)

    return mapping


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


def _wechat_wallet_rows(
    wechat_norm: pd.DataFrame,
    detail_to_bill_map: dict[str, list[str]],
    detail_to_group_map: dict[str, str],
) -> pd.DataFrame:
    df = wechat_norm.copy()
    df = _ensure_cols(
        df,
        [
            "pay_method",
            "amount",
            "direction",
            "trans_time",
            "trans_date",
            "counterparty",
            "item",
            "trans_type",
            "status",
            "trade_no",
            "merchant_no",
        ],
    )
    if df.empty:
        return _empty_unified_df()
    wallet = df.copy()
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
    wallet["match_status"] = ""
    wallet["remark_unified"] = wallet.apply(
        lambda r: _detail_match_remark(r, detail_to_bill_map),
        axis=1,
    )
    wallet["match_group_id"] = wallet.apply(
        lambda r: _detail_group_id(r, detail_to_group_map),
        axis=1,
    )
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
            "match_group_id": wallet["match_group_id"],
            "remark": wallet["remark_unified"],
        }
    )
    return out


def _alipay_wallet_rows(
    alipay_norm: pd.DataFrame,
    detail_to_bill_map: dict[str, list[str]],
    detail_to_group_map: dict[str, str],
) -> pd.DataFrame:
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
            "trade_no",
            "merchant_no",
        ],
    )
    if df.empty:
        return _empty_unified_df()
    wallet = df.copy()
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
    wallet["match_status"] = ""
    wallet["remark_unified"] = wallet.apply(
        lambda r: _detail_match_remark(r, detail_to_bill_map),
        axis=1,
    )
    wallet["match_group_id"] = wallet.apply(
        lambda r: _detail_group_id(r, detail_to_group_map),
        axis=1,
    )
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
            "match_group_id": wallet["match_group_id"],
            "remark": wallet["remark_unified"],
        }
    )
    return out


def _credit_card_rows(
    cc_enriched: pd.DataFrame,
    cc_unmatched: pd.DataFrame,
    detail_lookup: dict[str, list[str]],
) -> pd.DataFrame:
    cc = pd.concat([cc_enriched, cc_unmatched], ignore_index=True).fillna("")
    cc = _ensure_cols(
        cc,
        [
            "source",
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
    cc["primary_source"] = cc.get("source", "credit_card").map(lambda x: str(x).strip() or "credit_card")
    cc["account"] = cc.apply(lambda r: _cc_account(r.get("primary_source"), r.get("card_last4")), axis=1)
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
        lambda r: f"{r.get('primary_source','')}".strip() + "|" + str(r.get("detail_channel")).strip()
        if r.get("match_status") == "matched"
        else f"{r.get('primary_source','')}".strip(),
        axis=1,
    )
    def cc_remark(row: pd.Series) -> str:
        status = _clean_str(row.get("match_status"))
        if status == "matched":
            parts: list[str] = []
            match_sources = _clean_str(row.get("match_sources"))
            if match_sources:
                parts.append(f"多源匹配：{match_sources}")
            merge_refs = _detail_refs_for_row(row, detail_lookup)
            merge_text = _join_refs(merge_refs)
            if merge_text:
                parts.append(f"合并明细：{merge_text}")
            return "；".join(parts)
        if status:
            return f"未匹配明细：{status}"
        return ""

    cc["remark_unified"] = cc.apply(cc_remark, axis=1)

    def cc_group_id(row: pd.Series) -> str:
        if _clean_str(row.get("match_status")) != "matched":
            return ""
        ids = _extract_detail_ids(row)
        if ids:
            return _match_group_id_from_detail_ids(ids)
        return _match_group_id_from_bill(_bill_descriptor_cc(row))

    cc["match_group_id"] = cc.apply(cc_group_id, axis=1)

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
            "match_group_id": cc["match_group_id"],
            "remark": cc["remark_unified"],
        }
    )
    return out


def _bank_rows(
    bank_enriched: pd.DataFrame,
    bank_unmatched: pd.DataFrame,
    detail_lookup: dict[str, list[str]],
) -> pd.DataFrame:
    bank = pd.concat([bank_enriched, bank_unmatched], ignore_index=True).fillna("")
    bank = _ensure_cols(
        bank,
        [
            "source",
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
    bank["primary_source"] = bank.get("source", "bank_statement").map(lambda x: str(x).strip() or "bank_statement")
    bank["account"] = bank.apply(lambda r: _bank_account(r.get("primary_source"), r.get("account_last4")), axis=1)
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
        lambda r: f"{r.get('primary_source','')}".strip() + "|" + str(r.get("detail_channel")).strip()
        if r.get("match_status") == "matched"
        else f"{r.get('primary_source','')}".strip(),
        axis=1,
    )
    def bank_remark(row: pd.Series) -> str:
        status = _clean_str(row.get("match_status"))
        if status == "matched":
            parts: list[str] = []
            match_sources = _clean_str(row.get("match_sources"))
            if match_sources:
                parts.append(f"多源匹配：{match_sources}")
            merge_refs = _detail_refs_for_row(row, detail_lookup)
            merge_text = _join_refs(merge_refs)
            if merge_text:
                parts.append(f"合并明细：{merge_text}")
            return "；".join(parts)
        if status:
            return f"未匹配明细：{status}"
        return ""

    bank["remark_unified"] = bank.apply(bank_remark, axis=1)

    def bank_group_id(row: pd.Series) -> str:
        if _clean_str(row.get("match_status")) != "matched":
            return ""
        ids = _extract_detail_ids(row)
        if ids:
            return _match_group_id_from_detail_ids(ids)
        return _match_group_id_from_bill(_bill_descriptor_bank(row))

    bank["match_group_id"] = bank.apply(bank_group_id, axis=1)

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
            "match_group_id": bank["match_group_id"],
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
    period: Period | None = None,
) -> Path:
    cc_enriched = _read_csv_or_empty(cc_enriched_path, CC_ENRICHED_COLUMNS)
    cc_unmatched = _read_csv_or_empty(cc_unmatched_path, CC_UNMATCHED_COLUMNS)
    bank_enriched = _read_csv_or_empty(bank_enriched_path, BANK_ENRICHED_COLUMNS)
    bank_unmatched = _read_csv_or_empty(bank_unmatched_path, BANK_UNMATCHED_COLUMNS)
    wechat_norm = _read_csv_or_empty(wechat_norm_path, WECHAT_NORMALIZED_COLUMNS)
    alipay_norm = _read_csv_or_empty(alipay_norm_path, ALIPAY_NORMALIZED_COLUMNS)

    detail_lookup = _build_detail_lookup(wechat_norm, alipay_norm)
    detail_to_bill = _build_detail_to_bill_map(cc_enriched, bank_enriched)
    detail_to_group = _build_detail_to_group_map(cc_enriched, bank_enriched)

    cc_out = _credit_card_rows(cc_enriched, cc_unmatched, detail_lookup)
    bank_out = _bank_rows(bank_enriched, bank_unmatched, detail_lookup)
    wallet_out = pd.concat(
        [
            _wechat_wallet_rows(wechat_norm, detail_to_bill, detail_to_group),
            _alipay_wallet_rows(alipay_norm, detail_to_bill, detail_to_group),
        ],
        ignore_index=True,
    )

    all_txn = pd.concat([cc_out, bank_out, wallet_out], ignore_index=True)
    # 先按日期、再按时间排序（时间可能为空）。
    all_txn = all_txn.sort_values(by=["trade_date", "trade_time", "account"], ascending=True, kind="stable")

    out_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = out_dir / "unified.transactions.xlsx"
    csv_path = out_dir / "unified.transactions.csv"

    all_xlsx_path = out_dir / "unified.transactions.all.xlsx"
    all_csv_path = out_dir / "unified.transactions.all.csv"

    filtered_txn = all_txn

    if period is not None:
        start_date, end_date, label = period.start_date, period.end_date, period.label
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
    if period is not None:
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
    parser.add_argument("--period-day", type=int, default=20)
    parser.add_argument("--period-mode", type=str, default="billing")
    args = parser.parse_args()

    period: Period | None = None

    if args.period_year and args.period_month:
        year = int(args.period_year)
        month = int(args.period_month)
        if not (1 <= month <= 12):
            raise SystemExit("--period-month 必须在 1~12 之间")
        mode = str(args.period_mode or "billing").strip().lower()
        day = int(args.period_day or 20)
        if not (1 <= day <= 31):
            raise SystemExit("--period-day 必须在 1~31 之间")
        if mode == "calendar":
            last_day = calendar.monthrange(year, month)[1]
            start_date = date(year, month, 1)
            end_date = date(year, month, last_day)
            label = f"{year:04d}-{month:02d} 自然月"
        else:
            start_year, start_month = (year - 1, 12) if month == 1 else (year, month - 1)
            prev_last_day = calendar.monthrange(start_year, start_month)[1]
            end_last_day = calendar.monthrange(year, month)[1]
            prev_end_day = min(day, prev_last_day)
            end_day = min(day, end_last_day)
            prev_end_date = date(start_year, start_month, prev_end_day)
            start_date = prev_end_date + timedelta(days=1)
            end_date = date(year, month, end_day)
            label = f"{year:04d}-{month:02d} 信用卡账期({day}日)"
        period = Period(start_date=start_date, end_date=end_date, label=label)

    build_unified(
        cc_enriched_path=args.cc_enriched,
        cc_unmatched_path=args.cc_unmatched,
        bank_enriched_path=args.bank_enriched,
        bank_unmatched_path=args.bank_unmatched,
        wechat_norm_path=args.wechat,
        alipay_norm_path=args.alipay,
        out_dir=args.out_dir,
        period=period,
    )


if __name__ == "__main__":
    main()
