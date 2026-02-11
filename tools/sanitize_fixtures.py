from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

import pandas as pd
import pdfplumber

from openledger.parsers.pdf.cmb import detect_kind_from_text


KEEP_TOKENS = {
    # 解析器识别关键字
    "招商银行信用卡对账单",
    "招商银行交易流水",
    "CMB",
    "Credit",
    "Card",
    "Statement",
    "Transaction",
    "Details",
    "人民币账户",
    "交易日",
    "本期账务明细",
    "Transaction",
    "Details",
    "账单日",
    "账户类型",
    "账号",
    "户",
    "名",
    "Name",
    "Account",
    "Type",
    "Date",
    "Verification",
    "交易日期",
    "记账日期",
    "Currency",
    "Amount",
    "Balance",
    # 业务关键词
    "微信",
    "支付宝",
    "财付通",
    "退款",
    "还款",
    "消费",
    "分期",
    "费用",
    "利息",
    "其他",
    "信用卡",
    "储蓄卡",
    "银行卡",
    "收入",
    "支出",
    "不计收支",
    "快捷支付",
    "银联快捷支付",
    "快捷退款",
    "银联快捷退款",
}


TOKEN_RE = re.compile(
    r"-?\d[\d,]*\.\d{2}|\d{4}-\d{2}-\d{2}|\d{2}/\d{2}|[\u4e00-\u9fff]+|[A-Za-z]+|\d+"
)


class Anonymizer:
    def __init__(self) -> None:
        self.token_map: dict[str, str] = {}
        self.last4_map: dict[str, str] = {}
        self.digits_map: dict[str, str] = {}
        self.keep_tokens = KEEP_TOKENS.copy()
        self._next_last4 = 1000

    def map_last4(self, value: str) -> str:
        s = str(value).strip()
        if not s:
            return ""
        if s in self.last4_map:
            return self.last4_map[s]
        while True:
            self._next_last4 += 1
            cand = f"{self._next_last4:04d}"
            if cand != s and cand not in self.last4_map.values():
                self.last4_map[s] = cand
                return cand

    def map_digits(self, value: str) -> str:
        s = str(value).strip()
        if not s:
            return ""
        if s in self.digits_map:
            return self.digits_map[s]
        h = hashlib.sha1(s.encode("utf-8")).hexdigest()
        digits = "".join(str(int(h[i], 16) % 10) for i in range(len(s)))
        if digits == s:
            digits = digits[::-1]
        self.digits_map[s] = digits
        return digits

    def map_word(self, token: str) -> str:
        if token in self.token_map:
            return self.token_map[token]
        alias = f"T{len(self.token_map) + 1:04d}"
        self.token_map[token] = alias
        return alias

    def mask_text(self, text: str) -> str:
        if text is None:
            return ""
        raw = str(text)

        def repl(match: re.Match[str]) -> str:
            tok = match.group(0)
            if tok in self.keep_tokens:
                return tok
            if re.fullmatch(r"[A-Z]{2,3}", tok):
                return tok
            if re.fullmatch(r"-?\d[\d,]*\.\d{2}", tok):
                return tok
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", tok):
                return tok
            if re.fullmatch(r"\d{2}/\d{2}", tok):
                return tok
            if tok.isdigit():
                if len(tok) == 4:
                    return self.map_last4(tok)
                return self.map_digits(tok)
            return self.map_word(tok)

        return TOKEN_RE.sub(repl, raw)

    def mask_id(self, value: str) -> str:
        s = str(value).strip()
        if not s:
            return ""
        h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]
        return f"ID_{h}"

    def mask_pay_method(self, text: str) -> str:
        if text is None:
            return ""
        raw = str(text)
        parts = re.split(r"(信用卡|储蓄卡)", raw)
        masked = []
        for part in parts:
            if part in {"信用卡", "储蓄卡"}:
                masked.append(part)
            else:
                masked.append(self.mask_text(part))
        return "".join(masked)


def _detect_run(root: Path, run_id: str | None) -> Path:
    runs_dir = root / "runs"
    if run_id:
        cand = runs_dir / run_id
        if cand.exists():
            return cand
        raise SystemExit(f"run_id not found: {run_id}")
    if not runs_dir.exists():
        raise SystemExit("runs/ 目录不存在")
    runs = sorted(
        [p for p in runs_dir.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for r in runs:
        if (r / "output").exists():
            return r
    raise SystemExit("未找到可用的 run 目录")


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def _sanitize_df(df: pd.DataFrame, anon: Anonymizer) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        key = col.lower()
        if key in {"card_last4", "account_last4"}:
            out[col] = out[col].map(anon.map_last4)
            continue
        if key.endswith("_no") or key in {"trade_no", "merchant_no", "counterparty_account", "txn_id"}:
            out[col] = out[col].map(anon.mask_id)
            continue
        if key == "pay_method":
            out[col] = out[col].map(anon.mask_pay_method)
            continue
        if key in {
            "merchant",
            "counterparty",
            "item",
            "remark",
            "summary",
            "description",
            "account",
            "note",
            "reason",
            "detail_counterparty",
            "detail_item",
            "detail_pay_method",
            "detail_remark",
        }:
            out[col] = out[col].map(anon.mask_text)
            continue
    return out


def _split_pages(text: str) -> list[str]:
    if not text:
        return []
    return [p.strip("\n") for p in text.split("\n\n---PAGE---\n\n") if p.strip()]


def _extract_pdf_text(pdf_path: Path) -> list[str]:
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append((page.extract_text() or "").strip())
    return pages


def _write_pdf_text(pages: list[str], out_path: Path, anon: Anonymizer) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    masked_pages = [anon.mask_text(p) for p in pages]
    out_path.write_text("\n\n---PAGE---\n\n".join(masked_pages), encoding="utf-8")


def _parse_rows_from_text(kind: str, pages: list[str]) -> list[dict]:
    from openledger.parsers.pdf import cmb as cmb_parser

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

    original_open = cmb_parser.pdfplumber.open
    cmb_parser.pdfplumber.open = lambda _: _FakePdf(pages)
    try:
        return cmb_parser.extract_rows(Path("dummy.pdf"), kind)
    finally:
        cmb_parser.pdfplumber.open = original_open


def _pick_transactions_csv(out_dir: Path) -> dict[str, Path]:
    tx_csvs = sorted(out_dir.glob("*.transactions.csv"))
    if not tx_csvs:
        return {}
    cc_required = {"section", "trans_date", "post_date", "description", "amount_rmb", "card_last4"}
    bank_required = {"account_last4", "trans_date", "currency", "amount", "balance", "summary", "counterparty"}
    found: dict[str, Path] = {}
    for p in tx_csvs:
        try:
            header = _read_csv(p).columns
        except Exception:
            continue
        cols = set(header)
        if cc_required.issubset(cols) and "credit_card" not in found:
            found["credit_card"] = p
        if bank_required.issubset(cols) and "statement" not in found:
            found["statement"] = p
    return found


def _pick_pdfs(inputs_dir: Path) -> dict[str, Path]:
    pdfs = sorted(inputs_dir.glob("*.pdf"))
    picked: dict[str, Path] = {}
    for p in pdfs:
        try:
            pages = _extract_pdf_text(p)
            first = pages[0] if pages else ""
        except Exception:
            continue
        kind = detect_kind_from_text(first)
        if kind == "cmb_credit_card" and "credit_card" not in picked:
            picked["credit_card"] = p
        if kind == "cmb_statement" and "statement" not in picked:
            picked["statement"] = p
    return picked


def _write_meta(out_dir: Path, run_dir: Path) -> None:
    meta = {
        "source_run": run_dir.name,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sanitize fixtures from runs/* into tests/fixtures.")
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--out-dir", type=Path, default=Path("tests/fixtures/sample_run"))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    run_dir = _detect_run(root, args.run_id)
    out_dir = args.out_dir
    inputs_dir = run_dir / "inputs"
    outputs_dir = run_dir / "output"

    anon = Anonymizer()

    tx_files = _pick_transactions_csv(outputs_dir)
    if "credit_card" not in tx_files or "statement" not in tx_files:
        raise SystemExit("未找到信用卡/储蓄卡 transactions.csv（output/*.transactions.csv）")

    wechat_path = outputs_dir / "wechat.normalized.csv"
    alipay_path = outputs_dir / "alipay.normalized.csv"
    if not wechat_path.exists() or not alipay_path.exists():
        raise SystemExit("未找到 wechat/alipay 标准化输出（output/wechat.normalized.csv）")

    pdfs = _pick_pdfs(inputs_dir)
    if "credit_card" not in pdfs or "statement" not in pdfs:
        raise SystemExit("未找到可识别的 PDF（inputs/*.pdf）")

    out_inputs = out_dir / "inputs"
    out_expected = out_dir / "expected"
    out_expected_pdf = out_dir / "expected_pdf"
    out_pdf_text = out_dir / "pdf_text"

    cc_df = _sanitize_df(_read_csv(tx_files["credit_card"]), anon)
    bank_df = _sanitize_df(_read_csv(tx_files["statement"]), anon)
    wechat_df = _sanitize_df(_read_csv(wechat_path), anon)
    alipay_df = _sanitize_df(_read_csv(alipay_path), anon)

    _write_csv(cc_df, out_inputs / "cmb_credit_card.transactions.csv")
    _write_csv(bank_df, out_inputs / "cmb_statement.transactions.csv")
    _write_csv(wechat_df, out_inputs / "wechat.normalized.csv")
    _write_csv(alipay_df, out_inputs / "alipay.normalized.csv")

    # 生成匹配与统一输出的期望结果
    from stages.match_credit_card import match_credit_card
    from stages.match_bank import match_bank_statements
    from stages.build_unified import build_unified

    tmp_out = out_dir / "_generated"
    tmp_out.mkdir(parents=True, exist_ok=True)

    match_credit_card(
        credit_card_csv=out_inputs / "cmb_credit_card.transactions.csv",
        wechat_csv=out_inputs / "wechat.normalized.csv",
        alipay_csv=out_inputs / "alipay.normalized.csv",
        out_dir=tmp_out,
    )
    match_bank_statements(
        bank_csvs=[out_inputs / "cmb_statement.transactions.csv"],
        wechat_csv=out_inputs / "wechat.normalized.csv",
        alipay_csv=out_inputs / "alipay.normalized.csv",
        out_dir=tmp_out,
    )

    build_unified(
        cc_enriched_path=tmp_out / "credit_card.enriched.csv",
        cc_unmatched_path=tmp_out / "credit_card.unmatched.csv",
        bank_enriched_path=tmp_out / "bank.enriched.csv",
        bank_unmatched_path=tmp_out / "bank.unmatched.csv",
        wechat_norm_path=out_inputs / "wechat.normalized.csv",
        alipay_norm_path=out_inputs / "alipay.normalized.csv",
        out_dir=tmp_out,
    )

    for name in [
        "credit_card.enriched.csv",
        "credit_card.unmatched.csv",
        "bank.enriched.csv",
        "bank.unmatched.csv",
        "unified.transactions.csv",
    ]:
        src = tmp_out / name
        if src.exists():
            _write_csv(_read_csv(src), out_expected / name)

    # PDF text fixtures + parser expected outputs
    for kind, pdf_path in pdfs.items():
        pages = _extract_pdf_text(pdf_path)
        filename = "cmb_credit_card.txt" if kind == "credit_card" else "cmb_statement.txt"
        _write_pdf_text(pages, out_pdf_text / filename, anon)

        masked_pages = _split_pages((out_pdf_text / filename).read_text(encoding="utf-8"))
        parsed_rows = _parse_rows_from_text(
            "cmb_credit_card" if kind == "credit_card" else "cmb_statement",
            masked_pages,
        )
        _write_csv(pd.DataFrame(parsed_rows), out_expected_pdf / f"{filename}.csv")

    _write_meta(out_dir, run_dir)

    # 清理中间产物，避免误提交。
    import shutil

    shutil.rmtree(tmp_out, ignore_errors=True)


if __name__ == "__main__":
    main()
