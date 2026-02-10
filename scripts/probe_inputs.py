"""probe_inputs：探测微信/支付宝导出文件（表结构 + 预览）。

这是一个开发者工具，用于在编写解析器前快速确认导出文件格式。
它不会生成流水线产物。
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from _common import log, make_parser


def _print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def probe_wechat_xlsx(path: Path, *, max_rows: int = 10) -> None:
    _print_header(f"微信 xlsx: {path}")
    xl = pd.ExcelFile(path)
    print("工作表:", xl.sheet_names)
    for sheet in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet, nrows=max_rows)
        print(f"\n-- 工作表: {sheet} shape={df.shape}")
        print("列:", list(df.columns))
        print(df.head(min(5, len(df))).to_string(index=False))


def _find_alipay_header_line(lines: list[str]) -> int | None:
    for i, line in enumerate(lines):
        if "交易时间" in line and ("交易分类" in line or "交易对方" in line or "商品说明" in line or "商品名称" in line):
            return i
    return None


def probe_alipay_csv(path: Path, *, max_lines: int = 25) -> None:
    _print_header(f"支付宝 csv: {path}")
    raw = path.read_bytes()
    text = None
    for enc in ["utf-8-sig", "utf-8", "gb18030", "gbk"]:
        try:
            text = raw.decode(enc)
            print("编码:", enc)
            break
        except Exception:
            continue
    if text is None:
        raise RuntimeError("无法解码支付宝 CSV")

    lines = text.splitlines()
    print("总行数:", len(lines))
    print(f"前 {max_lines} 行:")
    for idx, line in enumerate(lines[:max_lines], 1):
        print(f"{idx:02d}: {line[:200]}")

    header_idx = _find_alipay_header_line(lines)
    print("表头行号:", header_idx)
    if header_idx is None:
        return
    header = lines[header_idx]
    print("表头内容:", header[:200])

    # 先用 csv 模块从表头行开始尝试解析。
    rows = list(csv.reader(lines[header_idx:]))
    print("csv 模块: 表头起始行数:", len(rows))
    if rows:
        print("csv 模块: 列:", rows[0])
        print("csv 模块: 样例行:", rows[1] if len(rows) > 1 else None)

    # 再用 pandas（python engine）尝试解析。
    try:
        df = pd.read_csv(path, skiprows=header_idx, engine="python")
        print("pandas 列:", list(df.columns))
        print("pandas 行数:", len(df))
        print(df.head(3).to_string(index=False))
    except Exception as exc:
        print("pandas read_csv 失败:", exc)


def main() -> None:
    parser = make_parser("探测微信/支付宝导出文件（表结构 + 预览）。")
    parser.add_argument("--wechat", type=Path, default=None, help="微信 xlsx 路径；不传则自动探测。")
    parser.add_argument("--alipay", type=Path, default=None, help="支付宝 csv 路径；不传则自动探测。")
    parser.add_argument("--max-rows", type=int, default=10, help="每个 sheet 最多预览多少行。")
    parser.add_argument("--max-lines", type=int, default=25, help="支付宝 csv 最多展示多少行原始文本。")
    args = parser.parse_args()

    wechat = args.wechat
    alipay = args.alipay

    if wechat is None:
        matches = sorted(Path(".").glob("微信支付账单流水文件*.xlsx"))
        wechat = matches[0] if matches else None
    if alipay is None:
        matches = sorted(Path(".").glob("支付宝交易明细*.csv"))
        alipay = matches[0] if matches else None

    if wechat is None and alipay is None:
        log("probe_inputs", "未检测到输入文件；请传 --wechat / --alipay")
        return

    if wechat:
        probe_wechat_xlsx(wechat, max_rows=args.max_rows)
    else:
        log("probe_inputs", "微信=缺少输入")

    if alipay:
        probe_alipay_csv(alipay, max_lines=args.max_lines)
    else:
        log("probe_inputs", "支付宝=缺少输入")


if __name__ == "__main__":
    main()
