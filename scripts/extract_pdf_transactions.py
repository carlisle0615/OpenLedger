"""extract_pdf：从支持的 PDF 中提取交易记录。

输入：
- 一个或多个 PDF 文件（可混合；auto 模式会对每个文件单独识别）。

输出：
- `<out-dir>/*.transactions.csv`

示例：
- `uv run python scripts/extract_pdf_transactions.py --out-dir output *.pdf`
- `uv run python scripts/extract_pdf_transactions.py --mode cmb --out-dir output *.pdf`
- `uv run python scripts/extract_pdf_transactions.py --list-modes`
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any, Iterable

import pdfplumber

from _common import log, make_parser

# 允许直接 `python scripts/xxx.py` 运行时也能 import openledger 包（不要求 pip 安装）。
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openledger.parsers.pdf import get_pdf_parser, iter_pdf_parsers, list_pdf_modes  # noqa: E402


def _write_csv(rows: Iterable[dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        out_path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_first_page_text(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            return ""
        return (pdf.pages[0].extract_text() or "").strip()


def _mode_help_lines() -> list[str]:
    lines = []
    for m in list_pdf_modes():
        lines.append(f"- {m['id']}: {m['name']}")
    return lines


def main() -> None:
    parser = make_parser("从支持的 PDF 中提取交易记录。")
    parser.add_argument("pdf", type=Path, nargs="*")
    parser.add_argument("--out-dir", type=Path, default=Path("output"), help="输出目录。")
    parser.add_argument(
        "--mode",
        type=str,
        default="auto",
        help="PDF 解析模式：auto（默认，自动识别）或指定解析器 id（例如 cmb）。",
    )
    parser.add_argument("--list-modes", action="store_true", help="列出当前支持的 PDF 解析模式并退出。")
    args = parser.parse_args()

    if args.list_modes:
        for m in list_pdf_modes():
            print(f"{m['id']}\t{m['name']}")
        return

    pdfs: list[Path] = list(args.pdf or [])
    if not pdfs:
        raise SystemExit("未提供 PDF 文件；请传入一个或多个 *.pdf，或使用 --list-modes 查看支持的解析器。")

    mode_id = (str(args.mode or "").strip() or "auto").lower()
    supported = [m["id"] for m in list_pdf_modes()]
    if mode_id != "auto" and mode_id not in supported:
        raise SystemExit(
            f"未知 --mode: {mode_id}\n"
            f"支持的 --mode: {', '.join(supported)}\n"
            "可用 `uv run python scripts/extract_pdf_transactions.py --list-modes` 查看详细列表。\n"
        )

    errors: list[str] = []

    for pdf_path in pdfs:
        out_path = args.out_dir / f"{pdf_path.stem}.transactions.csv"
        try:
            first_text = _read_first_page_text(pdf_path)
        except Exception as exc:
            msg = f"读取失败: {exc}"
            errors.append(f"{pdf_path}: {msg}")
            log("extract_pdf", f"失败 输入={pdf_path} 错误={msg}")
            continue

        parser_mod: Any | None = None
        kind: str | None = None

        if mode_id == "auto":
            for mod in iter_pdf_parsers():
                try:
                    k = mod.detect_kind_from_text(first_text)
                except Exception:
                    k = None
                if k:
                    parser_mod = mod
                    kind = k
                    break
        else:
            try:
                parser_mod = get_pdf_parser(mode_id)
            except KeyError:
                parser_mod = None
            if parser_mod is not None:
                kind = parser_mod.detect_kind_from_text(first_text)

        if parser_mod is None or not kind:
            msg = f"无法识别 PDF 类型（mode={mode_id}）"
            errors.append(f"{pdf_path}: {msg}")
            log("extract_pdf", f"失败 输入={pdf_path} 错误={msg}")
            continue

        try:
            rows = parser_mod.extract_rows(pdf_path, kind)
        except Exception as exc:
            msg = f"解析失败（mode={getattr(parser_mod,'MODE_ID','?')} kind={kind}）: {exc}"
            errors.append(f"{pdf_path}: {msg}")
            log("extract_pdf", f"失败 输入={pdf_path} 错误={msg}")
            continue

        _write_csv(rows, out_path)
        log(
            "extract_pdf",
            f"成功 mode={getattr(parser_mod,'MODE_ID','?')} kind={kind} 输入={pdf_path} 输出={out_path} 行数={len(rows)}",
        )

    # 严格失败策略：任意文件失败，则整个阶段失败（返回非 0）。
    if errors:
        log("extract_pdf", f"解析失败文件数={len(errors)}（严格模式：将退出并标记阶段失败）")
        for e in errors:
            log("extract_pdf", f"错误: {e}")
        log("extract_pdf", "支持的 --mode 列表：")
        for line in _mode_help_lines():
            log("extract_pdf", line)
        log("extract_pdf", "排查建议：先用 `uv run python scripts/probe_pdf.py <pdf路径>` 查看第一页是否能抽到文本。")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
