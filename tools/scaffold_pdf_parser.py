"""scaffold_pdf_parser：生成 PDF 解析器脚手架（模板 + 测试 + golden fixture）。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _normalize_id(value: str, *, label: str) -> str:
    out = str(value or "").strip().lower().replace("-", "_")
    if not _ID_RE.fullmatch(out):
        raise ValueError(f"{label} 非法: {value!r}（仅允许小写字母/数字/下划线，且必须字母开头）")
    return out


def _normalize_kinds(mode_id: str, raw: str) -> list[str]:
    items = [x.strip() for x in str(raw or "").split(",") if x.strip()]
    if not items:
        items = [f"{mode_id}_statement"]
    kinds: list[str] = []
    for item in items:
        kind = _normalize_id(item, label="kind")
        if kind not in kinds:
            kinds.append(kind)
    return kinds


def _to_camel_case(mode_id: str) -> str:
    parts = [p for p in mode_id.split("_") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts) or "Parser"


def _render_parser_py(mode_id: str, mode_name: str, kinds: list[str]) -> str:
    prefix = _to_camel_case(mode_id)
    kind_literals = ", ".join([f'"{k}"' for k in kinds])
    kinds_tuple = ", ".join([f'"{k}"' for k in kinds])
    sample_lines = "\n".join([f'    ("TODO: {k} 首页关键字示例", "{k}"),' for k in kinds])
    detect_blocks = "\n".join(
        [
            f'    if "TODO_{k.upper()}" in text:\n'
            f'        return "{k}"\n'
            for k in kinds
        ]
    ).rstrip()
    overload_blocks = "\n\n".join(
        [
            f'@overload\n'
            f'def extract_rows(pdf_path: Path, kind: Literal["{k}"]) -> list[{prefix}Row]: ...'
            for k in kinds
        ]
    )

    return f'''"""{mode_name} PDF 解析器（脚手架模板）。"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal, TypedDict, TypeAlias, overload

import pdfplumber

MODE_ID: Final[Literal["{mode_id}"]] = "{mode_id}"
MODE_NAME: Final[str] = "{mode_name}"

{prefix}Kind: TypeAlias = Literal[{kind_literals}]
SUPPORTED_KINDS: Final[tuple[{prefix}Kind, ...]] = ({kinds_tuple},)
FILENAME_HINTS: Final[tuple[str, ...]] = (
    "*TODO_文件名关键字*.pdf",
)
DETECT_SAMPLES: Final[tuple[tuple[str, {prefix}Kind], ...]] = (
{sample_lines}
)


class {prefix}Row(TypedDict):
    source: Literal["{mode_id}"]
    kind: {prefix}Kind
    raw_line: str


def detect_kind_from_text(first_page_text: str) -> {prefix}Kind | None:
    text = (first_page_text or "").strip()
{detect_blocks if detect_blocks else '    # TODO: 根据首页关键字返回对应 kind\n    pass'}
    return None


{overload_blocks}


def extract_rows(pdf_path: Path, kind: {prefix}Kind) -> list[{prefix}Row]:
    if kind not in SUPPORTED_KINDS:
        raise ValueError(f"不支持的 PDF kind: {{kind}}")

    # TODO: 按 kind 实现真实解析逻辑（表格/文本行抽取）。
    # 这里保留最小占位实现，方便先接上 golden fixture。
    rows: list[{prefix}Row] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                rows.append(
                    {{
                        "source": MODE_ID,
                        "kind": kind,
                        "raw_line": line,
                    }}
                )

    return rows
'''


def _render_test_py(mode_id: str, mode_name: str, kinds: list[str]) -> str:
    prefix = _to_camel_case(mode_id)
    kinds_literal = ", ".join([f'"{k}"' for k in kinds])
    return f'''import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from openledger.parsers.pdf.{mode_id} import extract_rows


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "pdf_parsers" / "{mode_id}"
PDF_TEXT_DIR = FIXTURES_DIR / "pdf_text"
EXPECTED_DIR = FIXTURES_DIR / "expected"
KINDS = [{kinds_literal}]


def _read_csv(path: Path) -> list[dict]:
    df = pd.read_csv(path, dtype=str).fillna("")
    return df.to_dict("records")


def _read_pages(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [p.strip("\\n") for p in text.split("\\n\\n---PAGE---\\n\\n") if p.strip()]


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakePdf:
    def __init__(self, pages: list[str]) -> None:
        self.pages = [_FakePage(p) for p in pages]

    def __enter__(self) -> "_FakePdf":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


@unittest.skip("TODO: 完成 parser 逻辑并填充 fixture 后，去掉 skip。")
class Test{prefix}PdfParserGolden(unittest.TestCase):
    def test_parser_golden(self) -> None:
        for kind in KINDS:
            with self.subTest(kind=kind):
                pages = _read_pages(PDF_TEXT_DIR / f"{{kind}}.txt")
                expected = _read_csv(EXPECTED_DIR / f"{{kind}}.csv")
                with patch("openledger.parsers.pdf.{mode_id}.pdfplumber.open", return_value=_FakePdf(pages)):
                    rows = extract_rows(Path("dummy.pdf"), kind)
                self.assertEqual(rows, expected)
'''


def _render_fixture_readme(mode_id: str, mode_name: str, kinds: list[str]) -> str:
    kind_bullets = "\n".join([f"- `{k}`" for k in kinds])
    return f"""# {mode_name} Fixture 模板

该目录用于 `{mode_id}` parser 的 golden fixture。

## Kind 列表
{kind_bullets}

## 目录结构
- `pdf_text/<kind>.txt`：按 `---PAGE---` 分隔页文本
- `expected/<kind>.csv`：对应解析输出（UTF-8，首行为表头）

## 建议流程
1. 用真实 PDF 跑 `tools/probe_pdf.py`，提取并清洗页文本到 `pdf_text/`。
2. 实现 parser 后导出解析结果写入 `expected/`。
3. 去掉测试文件中的 `@unittest.skip`，执行：
   `uv run python -m unittest tests/test_pdf_{mode_id}_golden.py`
"""


def _write_file(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def scaffold(root: Path, mode_id: str, mode_name: str, kinds: list[str], *, force: bool) -> dict[str, list[str]]:
    parser_py = root / "openledger" / "parsers" / "pdf" / f"{mode_id}.py"
    test_py = root / "tests" / f"test_pdf_{mode_id}_golden.py"
    fixture_root = root / "tests" / "fixtures" / "pdf_parsers" / mode_id
    fixture_readme = fixture_root / "README.md"

    created: list[str] = []
    skipped: list[str] = []

    files = [
        (parser_py, _render_parser_py(mode_id, mode_name, kinds)),
        (test_py, _render_test_py(mode_id, mode_name, kinds)),
        (fixture_readme, _render_fixture_readme(mode_id, mode_name, kinds)),
    ]
    for path, content in files:
        if _write_file(path, content, force=force):
            created.append(str(path))
        else:
            skipped.append(str(path))

    for kind in kinds:
        txt_path = fixture_root / "pdf_text" / f"{kind}.txt"
        csv_path = fixture_root / "expected" / f"{kind}.csv"
        txt_content = (
            "TODO: 第1页文本（按实际内容替换）\n\n"
            "---PAGE---\n\n"
            "TODO: 第2页文本（可选）\n"
        )
        csv_content = "source,kind,raw_line\n"
        if _write_file(txt_path, txt_content, force=force):
            created.append(str(txt_path))
        else:
            skipped.append(str(txt_path))
        if _write_file(csv_path, csv_content, force=force):
            created.append(str(csv_path))
        else:
            skipped.append(str(csv_path))

    return {"created": created, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="生成 PDF parser 脚手架（parser + golden test + fixture 占位文件）。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--mode-id", required=True, help="解析器 mode id，例如 boc。")
    parser.add_argument("--mode-name", required=True, help="解析器显示名称。")
    parser.add_argument(
        "--kinds",
        default="",
        help="逗号分隔的 kind 列表，例如 boc_credit_card,boc_statement；不传默认 <mode_id>_statement。",
    )
    parser.add_argument("--root", type=Path, default=Path("."), help="仓库根目录。")
    parser.add_argument("--force", action="store_true", help="覆盖已存在文件。")
    args = parser.parse_args()

    mode_id = _normalize_id(args.mode_id, label="mode_id")
    mode_name = str(args.mode_name or "").strip()
    if not mode_name:
        raise SystemExit("mode_name 不能为空")
    kinds = _normalize_kinds(mode_id, args.kinds)

    result = scaffold(args.root.resolve(), mode_id, mode_name, kinds, force=args.force)
    print("[scaffold_pdf_parser] 已创建:")
    for path in result["created"]:
        print(f"  + {path}")
    if result["skipped"]:
        print("[scaffold_pdf_parser] 已跳过（文件已存在，可加 --force 覆盖）:")
        for path in result["skipped"]:
            print(f"  - {path}")

    print("\n后续请手动完成：")
    print("1) 在 openledger/parsers/pdf/__init__.py 注册新 parser（mode/kind/type alias）。")
    print("2) 实现 detect_kind_from_text / extract_rows。")
    print("3) 补齐 fixture 并移除测试文件中的 @unittest.skip。")


if __name__ == "__main__":
    main()
