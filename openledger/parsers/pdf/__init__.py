"""PDF 解析器 registry。

目标：
- 把“识别 + 解析”的实现抽离成可插拔模块，便于未来支持多银行/多格式。
- 对外提供稳定的 mode 列表（供 CLI/UI 渲染），以及按 mode_id 获取解析器。
"""

from __future__ import annotations

from typing import Any

from . import cmb


def iter_pdf_parsers() -> list[Any]:
    """返回已注册的 PDF 解析器模块列表（不包含 auto）。"""

    return [cmb]


def get_pdf_parser(mode_id: str) -> Any:
    """根据 mode_id 获取解析器模块。"""

    mode_id = str(mode_id or "").strip().lower()
    for parser in iter_pdf_parsers():
        if getattr(parser, "MODE_ID", None) == mode_id:
            return parser
    raise KeyError(f"未知 PDF mode: {mode_id}")


def list_pdf_modes() -> list[dict[str, str]]:
    """列出 UI/CLI 用的 mode 列表（包含 auto）。"""

    modes: list[dict[str, str]] = [{"id": "auto", "name": "自动识别（推荐）"}]
    for parser in iter_pdf_parsers():
        modes.append(
            {
                "id": str(getattr(parser, "MODE_ID", "")),
                "name": str(getattr(parser, "MODE_NAME", "")),
            }
        )
    # 过滤掉异常/未配置的解析器条目，避免 UI 渲染出现空值。
    return [m for m in modes if m.get("id") and m.get("name")]
