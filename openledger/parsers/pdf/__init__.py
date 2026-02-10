"""PDF 解析器 registry。

目标：
- 把“识别 + 解析”的实现抽离成可插拔模块，便于未来支持多银行/多格式。
- 对外提供稳定的 mode 列表（供 CLI/UI 渲染），以及按 mode_id 获取解析器。

类型策略（偏 TypeScript 风格）：
- mode/kind 使用 Literal 联合类型，新增解析器时需要显式扩展类型别名；
- 输出行使用 TypedDict，避免 `dict[str, str]` 这类“宽泛”类型。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final, Literal, TypedDict, TypeAlias

from .cmb import (
    MODE_ID as CMB_MODE_ID,
    MODE_NAME as CMB_MODE_NAME,
    CmbKind,
    CmbRow,
    detect_kind_from_text as cmb_detect_kind_from_text,
    extract_rows as cmb_extract_rows,
)

# =====================
# 公开类型（请显式扩展）
# =====================

# 注意：新增解析器时，请在这里把 mode id 加入 Literal 联合类型。
PdfParserModeId: TypeAlias = Literal["cmb"]
PdfParserModeIdOrAuto: TypeAlias = Literal["auto", "cmb"]

# 注意：新增解析器时，请在这里把 kind 加入联合类型。
PdfParserKind: TypeAlias = CmbKind

# 注意：新增解析器时，请在这里把 row 类型加入联合类型。
PdfRow: TypeAlias = CmbRow


class PdfModeItem(TypedDict):
    id: PdfParserModeIdOrAuto
    name: str


@dataclass(frozen=True, slots=True)
class PdfParser:
    mode_id: PdfParserModeId
    mode_name: str
    detect_kind_from_text: Callable[[str], PdfParserKind | None]
    extract_rows: Callable[[Path, PdfParserKind], list[PdfRow]]


# =====================
# 解析器注册（显式）
# =====================

CMB_PARSER: Final[PdfParser] = PdfParser(
    mode_id=CMB_MODE_ID,
    mode_name=CMB_MODE_NAME,
    detect_kind_from_text=cmb_detect_kind_from_text,
    extract_rows=cmb_extract_rows,
)

_PARSERS: Final[tuple[PdfParser, ...]] = (CMB_PARSER,)


def iter_pdf_parsers() -> tuple[PdfParser, ...]:
    """返回已注册的 PDF 解析器列表（不包含 auto）。"""

    return _PARSERS


def get_pdf_parser(mode_id: PdfParserModeId) -> PdfParser:
    """根据 mode_id 获取解析器。"""

    match mode_id:
        case "cmb":
            return CMB_PARSER
        case _:
            # 仅作为运行时防御：对类型检查器来说该分支不可达。
            raise KeyError(f"未知 PDF mode: {mode_id}")


def parse_pdf_mode_id(value: str) -> PdfParserModeIdOrAuto:
    """把用户输入的字符串解析成合法的 mode id。"""

    v = str(value or "").strip().lower()
    if not v:
        v = "auto"

    match v:
        case "auto":
            return "auto"
        case "cmb":
            return "cmb"
        case _:
            raise ValueError(f"未知 PDF mode: {value!r}")


def list_pdf_modes() -> list[PdfModeItem]:
    """列出 UI/CLI 用的 mode 列表（包含 auto）。"""

    modes: list[PdfModeItem] = [{"id": "auto", "name": "自动识别（推荐）"}]
    for parser in iter_pdf_parsers():
        modes.append({"id": parser.mode_id, "name": parser.mode_name})
    return modes

