from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd


def _to_decimal_amount(value: str) -> Decimal:
    cleaned = str(value).strip()
    cleaned = cleaned.replace("¥", "").replace("￥", "").replace(",", "").strip()
    if cleaned in {"", "nan", "NaN", "None"}:
        raise ValueError(f"Empty amount: {value!r}")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid amount: {value!r}") from exc


def _find_wechat_header_row(df: pd.DataFrame) -> int | None:
    # WeChat export has meta rows, then a header row containing 交易时间/交易类型...
    as_str = df.astype(str)
    mask = as_str.apply(lambda c: c.str.fullmatch("交易时间", na=False))
    hits = list(as_str.index[mask.any(axis=1)])
    return hits[0] if hits else None


def extract_wechat_xlsx(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, header=None)
    header_row = _find_wechat_header_row(raw)
    if header_row is None:
        raise ValueError("Cannot find WeChat header row (交易时间).")

    header = [str(v).strip() for v in raw.iloc[header_row].tolist()]
    df = raw.iloc[header_row + 1 :].copy()
    df.columns = header

    time_col = "交易时间"
    if time_col not in df.columns:
        raise ValueError("WeChat xlsx missing 交易时间 column after header parse.")

    df = df.dropna(subset=[time_col])

    amount_col = "金额(元)" if "金额(元)" in df.columns else ("金额" if "金额" in df.columns else None)
    if not amount_col:
        raise ValueError("WeChat xlsx missing amount column (金额/金额(元)).")

    df = df.rename(
        columns={
            "交易类型": "trans_type",
            "交易对方": "counterparty",
            "商品": "item",
            "收/支": "direction",
            amount_col: "amount",
            "支付方式": "pay_method",
            "当前状态": "status",
            "交易单号": "trade_no",
            "商户单号": "merchant_no",
            "备注": "remark",
        }
    )

    df["channel"] = "wechat"
    df["trans_time"] = pd.to_datetime(df[time_col], errors="coerce")
    df["trans_date"] = df["trans_time"].dt.date
    df["amount"] = df["amount"].map(_to_decimal_amount)

    keep = [
        "channel",
        "trans_time",
        "trans_date",
        "trans_type",
        "counterparty",
        "item",
        "direction",
        "amount",
        "pay_method",
        "status",
        "trade_no",
        "merchant_no",
        "remark",
    ]
    for col in keep:
        if col not in df.columns:
            df[col] = ""
    return df[keep].reset_index(drop=True)


def _detect_text_encoding(raw: bytes) -> str:
    for enc in ["utf-8-sig", "utf-8", "gb18030", "gbk"]:
        try:
            raw.decode(enc)
            return enc
        except Exception:
            continue
    return "gb18030"


def _find_alipay_header_idx(lines: list[str]) -> int | None:
    for i, line in enumerate(lines):
        if "交易时间" in line and ("交易分类" in line or "交易对方" in line or "商品说明" in line):
            return i
    return None


def extract_alipay_csv(path: Path) -> pd.DataFrame:
    raw = path.read_bytes()
    enc = _detect_text_encoding(raw)
    text = raw.decode(enc)
    lines = text.splitlines()
    header_idx = _find_alipay_header_idx(lines)
    if header_idx is None:
        raise ValueError("Cannot find Alipay header line (交易时间...).")

    df = pd.read_csv(
        path,
        encoding=enc,
        skiprows=header_idx,
        engine="python",
        dtype=str,
    )

    # Drop trailing empty column (header ends with a comma).
    df = df.loc[:, [c for c in df.columns if c and not str(c).startswith("Unnamed")]]

    # Normalize whitespace/tabs in ids.
    for col in ["交易订单号", "商家订单号"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.replace("\t", "", regex=False)

    df = df.rename(
        columns={
            "交易分类": "category",
            "交易对方": "counterparty",
            "对方账号": "counterparty_account",
            "商品说明": "item",
            "收/支": "direction",
            "金额": "amount",
            "收/付款方式": "pay_method",
            "交易状态": "status",
            "交易订单号": "trade_no",
            "商家订单号": "merchant_no",
            "备注": "remark",
        }
    )

    df["channel"] = "alipay"
    df["trans_time"] = pd.to_datetime(df["交易时间"], errors="coerce") if "交易时间" in df.columns else pd.NaT
    df["trans_date"] = df["trans_time"].dt.date
    df["amount"] = df["amount"].map(_to_decimal_amount)

    keep = [
        "channel",
        "trans_time",
        "trans_date",
        "category",
        "counterparty",
        "counterparty_account",
        "item",
        "direction",
        "amount",
        "pay_method",
        "status",
        "trade_no",
        "merchant_no",
        "remark",
    ]
    for col in keep:
        if col not in df.columns:
            df[col] = ""
    return df[keep].reset_index(drop=True)


def _write_csv(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_out = df.copy()
    # Ensure stable string serialization for Decimal + datetime.
    for col in df_out.columns:
        df_out[col] = df_out[col].map(lambda v: "" if v is None else str(v))
    df_out.to_csv(out_path, index=False, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract WeChat/Alipay exports to normalized CSV.")
    parser.add_argument("--wechat", type=Path, default=None)
    parser.add_argument("--alipay", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=Path("output"))
    args = parser.parse_args()

    if args.wechat is None:
        matches = sorted(Path(".").glob("微信支付账单流水文件*.xlsx"))
        args.wechat = matches[0] if matches else None
    if args.alipay is None:
        matches = sorted(Path(".").glob("支付宝交易明细*.csv"))
        args.alipay = matches[0] if matches else None

    if args.wechat:
        df_w = extract_wechat_xlsx(args.wechat)
        out = args.out_dir / "wechat.normalized.csv"
        _write_csv(df_w, out)
        print(f"[wechat] {args.wechat} -> {out} rows={len(df_w)}")
    else:
        print("[wechat] missing input")

    if args.alipay:
        df_a = extract_alipay_csv(args.alipay)
        out = args.out_dir / "alipay.normalized.csv"
        _write_csv(df_a, out)
        print(f"[alipay] {args.alipay} -> {out} rows={len(df_a)}")
    else:
        print("[alipay] missing input")


if __name__ == "__main__":
    main()
