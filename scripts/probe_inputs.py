from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd


def probe_wechat_xlsx(path: Path) -> None:
    print("\n" + "=" * 80)
    print("WeChat xlsx:", path)
    print("=" * 80)
    xl = pd.ExcelFile(path)
    print("sheets:", xl.sheet_names)
    for sheet in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet, nrows=10)
        print(f"\n-- sheet: {sheet} shape={df.shape}")
        print("columns:", list(df.columns))
        print(df.head(5).to_string(index=False))


def _find_alipay_header_line(lines: list[str]) -> int | None:
    for i, line in enumerate(lines):
        if "交易时间" in line and ("交易分类" in line or "交易对方" in line or "商品名称" in line):
            return i
    return None


def probe_alipay_csv(path: Path) -> None:
    print("\n" + "=" * 80)
    print("Alipay csv:", path)
    print("=" * 80)
    raw = path.read_bytes()
    text = None
    for enc in ["utf-8-sig", "utf-8", "gb18030", "gbk"]:
        try:
            text = raw.decode(enc)
            print("encoding:", enc)
            break
        except Exception:
            continue
    if text is None:
        raise RuntimeError("Cannot decode Alipay CSV")

    lines = text.splitlines()
    print("total lines:", len(lines))
    print("first 25 lines:")
    for idx, line in enumerate(lines[:25], 1):
        print(f"{idx:02d}: {line[:200]}")

    header_idx = _find_alipay_header_line(lines)
    print("header_idx:", header_idx)
    if header_idx is None:
        return
    header = lines[header_idx]
    print("header line:", header[:200])

    # Try to parse from header onwards with csv module first.
    rows = list(csv.reader(lines[header_idx:]))
    print("csv reader: rows from header:", len(rows))
    if rows:
        print("csv reader: columns:", rows[0])
        print("csv reader: sample row:", rows[1] if len(rows) > 1 else None)

    # Then try pandas with python engine.
    try:
        df = pd.read_csv(path, skiprows=header_idx, engine="python")
        print("pandas columns:", list(df.columns))
        print("pandas rows:", len(df))
        print(df.head(3).to_string(index=False))
    except Exception as exc:
        print("pandas read_csv failed:", exc)


def main() -> None:
    wechat = Path("微信支付账单流水文件(20260101-20260207)_20260207162500.xlsx")
    alipay = Path("支付宝交易明细(20251107-20260207).csv")

    if wechat.exists():
        probe_wechat_xlsx(wechat)
    else:
        print("missing:", wechat)

    if alipay.exists():
        probe_alipay_csv(alipay)
    else:
        print("missing:", alipay)


if __name__ == "__main__":
    main()
