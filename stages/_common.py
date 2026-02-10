from __future__ import annotations

"""阶段公共工具（统一日志与 CLI 风格）。"""

import argparse
from pathlib import Path


def make_parser(description: str) -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )


_STAGE_NAME: dict[str, str] = {
    "extract_pdf": "提取PDF",
    "extract_exports": "解析导出",
    "match_credit_card": "信用卡匹配",
    "match_bank": "借记卡匹配",
    "build_unified": "生成统一表",
    "classify": "分类",
    "finalize": "最终合并",
    "batch_ignore": "批量忽略",
    "probe_inputs": "输入探测",
    "probe_pdf": "PDF探测",
}


def log(stage: str, message: str) -> None:
    tag = _STAGE_NAME.get(stage, stage)
    print(f"[{tag}] {message}", flush=True)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
