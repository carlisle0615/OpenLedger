from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from openledger.parsers.pdf import PdfParser, iter_pdf_parsers
from openledger.state import utc_now_iso


class SourceSupportItem(TypedDict):
    id: str
    name: str
    channel: str
    file_types: list[str]
    filename_hints: list[str]
    stage: str
    parser_mode: str
    support_level: Literal["stable", "beta", "planned"]
    notes: str


class ParserDetectSampleCheck(TypedDict):
    index: int
    expected_kind: str
    detected_kind: str
    ok: bool


class PdfParserHealthItem(TypedDict):
    mode_id: str
    mode_name: str
    status: Literal["ok", "warning", "error"]
    kinds: list[str]
    filename_hints: list[str]
    sample_checks: list[ParserDetectSampleCheck]
    warnings: list[str]
    errors: list[str]


@dataclass(frozen=True, slots=True)
class _SourceSupportDef:
    id: str
    name: str
    channel: str
    file_types: tuple[str, ...]
    filename_hints: tuple[str, ...]
    stage: str
    parser_mode: str
    support_level: Literal["stable", "beta", "planned"]
    notes: str


_SOURCE_SUPPORT_DEFS: tuple[_SourceSupportDef, ...] = (
    _SourceSupportDef(
        id="wechat_xlsx",
        name="微信支付账单流水",
        channel="wechat",
        file_types=(".xlsx",),
        filename_hints=("微信支付账单流水文件*.xlsx",),
        stage="extract_exports",
        parser_mode="",
        support_level="stable",
        notes="手机端导出（本地解析）。",
    ),
    _SourceSupportDef(
        id="alipay_csv",
        name="支付宝交易明细",
        channel="alipay",
        file_types=(".csv",),
        filename_hints=("支付宝交易明细*.csv",),
        stage="extract_exports",
        parser_mode="",
        support_level="stable",
        notes="手机端导出（本地解析）。",
    ),
    _SourceSupportDef(
        id="cmb_credit_card_pdf",
        name="招商银行信用卡账单 PDF",
        channel="cmb_credit_card",
        file_types=(".pdf",),
        filename_hints=("*信用卡账单*.pdf",),
        stage="extract_pdf",
        parser_mode="cmb",
        support_level="stable",
        notes="由 `cmb` 解析器识别为 `cmb_credit_card`。",
    ),
    _SourceSupportDef(
        id="cmb_statement_pdf",
        name="招商银行交易流水 PDF",
        channel="cmb_statement",
        file_types=(".pdf",),
        filename_hints=("*招商银行交易流水*.pdf",),
        stage="extract_pdf",
        parser_mode="cmb",
        support_level="stable",
        notes="由 `cmb` 解析器识别为 `cmb_statement`。",
    ),
)


def list_source_support_matrix() -> list[SourceSupportItem]:
    out: list[SourceSupportItem] = []
    for item in _SOURCE_SUPPORT_DEFS:
        out.append(
            {
                "id": item.id,
                "name": item.name,
                "channel": item.channel,
                "file_types": list(item.file_types),
                "filename_hints": list(item.filename_hints),
                "stage": item.stage,
                "parser_mode": item.parser_mode,
                "support_level": item.support_level,
                "notes": item.notes,
            }
        )
    return out


def _parser_health_item(parser: PdfParser) -> PdfParserHealthItem:
    warnings: list[str] = []
    errors: list[str] = []
    sample_checks: list[ParserDetectSampleCheck] = []

    if not callable(parser.detect_kind_from_text):
        errors.append("detect_kind_from_text 不是可调用对象。")
    if not callable(parser.extract_rows):
        errors.append("extract_rows 不是可调用对象。")
    if not parser.kinds:
        warnings.append("未声明 kinds；建议显式声明支持的 PDF kind。")
    if not parser.filename_hints:
        warnings.append("未声明 filename_hints；UI 侧无法给出上传提示。")
    if not parser.detect_samples:
        warnings.append("未声明 detect_samples；无法做 detect 冒烟检查。")

    for idx, (sample_text, expected_kind) in enumerate(parser.detect_samples, start=1):
        detected_kind = ""
        ok = False
        try:
            got = parser.detect_kind_from_text(sample_text)
            detected_kind = str(got or "")
            ok = got == expected_kind
            if not ok:
                warnings.append(
                    f"detect_samples[{idx}] 期望 {expected_kind}，实际 {detected_kind or 'None'}。"
                )
        except Exception as exc:
            errors.append(f"detect_samples[{idx}] 执行异常: {exc}")
        sample_checks.append(
            {
                "index": idx,
                "expected_kind": str(expected_kind),
                "detected_kind": detected_kind,
                "ok": ok,
            }
        )

    if parser.kinds:
        known = set(parser.kinds)
        for _, expected_kind in parser.detect_samples:
            if expected_kind not in known:
                warnings.append(f"detect_samples 声明了未知 kind: {expected_kind}")

    status: Literal["ok", "warning", "error"] = "ok"
    if errors:
        status = "error"
    elif warnings:
        status = "warning"

    return {
        "mode_id": parser.mode_id,
        "mode_name": parser.mode_name,
        "status": status,
        "kinds": [str(k) for k in parser.kinds],
        "filename_hints": list(parser.filename_hints),
        "sample_checks": sample_checks,
        "warnings": warnings,
        "errors": errors,
    }


def get_pdf_parser_health() -> dict[str, Any]:
    items = [_parser_health_item(p) for p in iter_pdf_parsers()]
    summary = {
        "total": len(items),
        "ok": sum(1 for x in items if x["status"] == "ok"),
        "warning": sum(1 for x in items if x["status"] == "warning"),
        "error": sum(1 for x in items if x["status"] == "error"),
    }
    return {
        "summary": summary,
        "parsers": items,
    }


def get_capabilities_payload() -> dict[str, Any]:
    return {
        "generated_at": utc_now_iso(),
        "source_support_matrix": list_source_support_matrix(),
        "pdf_parser_health": get_pdf_parser_health(),
    }

