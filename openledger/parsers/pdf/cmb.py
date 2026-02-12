"""招商银行 PDF 解析器（信用卡对账单 / 交易流水）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final, Literal, TypedDict, TypeAlias, overload

import pdfplumber

MODE_ID: Final[Literal["cmb"]] = "cmb"
MODE_NAME: Final[str] = "招商银行（信用卡对账单/交易流水）"

CmbKind: TypeAlias = Literal["cmb_credit_card", "cmb_statement"]
SUPPORTED_KINDS: Final[tuple[CmbKind, ...]] = ("cmb_credit_card", "cmb_statement")
FILENAME_HINTS: Final[tuple[str, ...]] = (
    "*信用卡账单*.pdf",
    "*招商银行交易流水*.pdf",
)
DETECT_SAMPLES: Final[tuple[tuple[str, CmbKind], ...]] = (
    ("招商银行信用卡对账单\n账单日 2024年06月20日", "cmb_credit_card"),
    ("Transaction Statement of China Merchants Bank\n招商银行交易流水", "cmb_statement"),
)


class CmbCreditCardRow(TypedDict):
    source: Literal["cmb_credit_card"]
    section: str
    trans_date: str
    post_date: str
    description: str
    amount_rmb: str
    card_last4: str
    original_amount: str
    original_region: str


class CmbStatementRow(TypedDict):
    source: Literal["cmb_statement"]
    account_last4: str
    trans_date: str
    currency: str
    amount: str
    balance: str
    summary: str
    counterparty: str


CmbRow: TypeAlias = CmbCreditCardRow | CmbStatementRow


def detect_kind_from_text(first_page_text: str) -> CmbKind | None:
    text = (first_page_text or "").strip()
    if "招商银行信用卡对账单" in text or "CMB Credit Card Statement" in text:
        return "cmb_credit_card"
    if "招商银行交易流水" in text or "Transaction Statement of China Merchants Bank" in text:
        return "cmb_statement"
    return None


def _to_decimal(value: str) -> Decimal:
    cleaned = value.replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:  # pragma: no cover - 防御性分支
        raise ValueError(f"无效的小数: {value!r}") from exc


def _parse_statement_year_month(text: str) -> tuple[int, int] | None:
    match = re.search(r"CMB Credit Card Statement \((\d{4})\.(\d{2})\)", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"账单日\s*(\d{4})年(\d{2})月(\d{2})日", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"（.*?(\d{4})年(\d{2})月.*?）", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def _infer_year(statement_year: int, statement_month: int, month: int) -> int:
    if month > statement_month:
        return statement_year - 1
    return statement_year


_CC_SECTION = Literal["还款", "退款", "消费", "分期", "费用", "利息", "其他"]


@dataclass(frozen=True)
class CreditCardTxn:
    section: str
    trans_date: date
    post_date: date | None
    description: str
    amount_rmb: Decimal
    card_last4: str | None
    original_amount: Decimal | None
    original_region: str | None


def extract_cmb_credit_card_statement(pdf_path: Path) -> list[CreditCardTxn]:
    with pdfplumber.open(pdf_path) as pdf:
        first_text = (pdf.pages[0].extract_text() or "").strip()
        ym = _parse_statement_year_month(first_text)
        if not ym:
            raise ValueError("无法从第一页识别账单年月。")
        statement_year, statement_month = ym

        section: _CC_SECTION | None = None
        txns: list[CreditCardTxn] = []

        in_details = False
        date_line_re = re.compile(r"^(?P<m1>\d{2})/(?P<d1>\d{2})(?:\s+(?P<m2>\d{2})/(?P<d2>\d{2}))?\s+")
        tail_re = re.compile(
            r"(?P<desc>.+?)\s+"
            r"(?P<amount>-?\d[\d,]*\.\d{2})\s+"
            r"(?:(?P<last4>\d{4})\s+)?"
            r"(?P<orig>-?\d[\d,]*\.\d{2})(?:\((?P<region>[A-Z]{2})\))?$"
        )

        for page in pdf.pages:
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

            for line in lines:
                if "本期账务明细" in line or "Transaction Details" in line:
                    in_details = True
                    continue
                if not in_details:
                    continue

                if line in {"还款", "退款", "消费", "分期", "费用", "利息", "其他"}:
                    section = line  # type: ignore[assignment]
                    continue

                if line.startswith(("招商银行信用卡对账单", "人民币账户", "交易日", "Trans", "Description")):
                    continue

                m = date_line_re.match(line)
                if not m:
                    continue

                m1 = int(m.group("m1"))
                d1 = int(m.group("d1"))
                m2 = m.group("m2")
                d2 = m.group("d2")

                y1 = _infer_year(statement_year, statement_month, m1)
                trans_date = date(y1, m1, d1)

                post_date: date | None
                if m2 and d2:
                    m2i = int(m2)
                    d2i = int(d2)
                    y2 = _infer_year(statement_year, statement_month, m2i)
                    post_date = date(y2, m2i, d2i)
                else:
                    post_date = None

                rest = line[m.end() :].strip()
                tail = tail_re.match(rest)
                if not tail:
                    # 部分长描述会换行，尽量用更宽松的策略兜底解析。
                    parts = rest.split()
                    if len(parts) < 3:
                        continue
                    try:
                        amount_rmb = _to_decimal(parts[-3])
                        card_last4 = parts[-2] if re.fullmatch(r"\d{4}", parts[-2]) else None
                        orig_raw = parts[-1]
                        orig_match = re.fullmatch(
                            r"(?P<orig>-?\d[\d,]*\.\d{2})(?:\((?P<region>[A-Z]{2})\))?",
                            orig_raw,
                        )
                        original_amount = _to_decimal(orig_match.group("orig")) if orig_match else None
                        original_region = orig_match.group("region") if orig_match else None
                    except Exception:
                        continue
                    description = " ".join(parts[: -3 if card_last4 else -2]).strip()
                else:
                    description = tail.group("desc").strip()
                    amount_rmb = _to_decimal(tail.group("amount"))
                    card_last4 = tail.group("last4")
                    original_amount = _to_decimal(tail.group("orig"))
                    original_region = tail.group("region")

                txns.append(
                    CreditCardTxn(
                        section=section or "其他",
                        trans_date=trans_date,
                        post_date=post_date,
                        description=description,
                        amount_rmb=amount_rmb,
                        card_last4=card_last4,
                        original_amount=original_amount,
                        original_region=original_region,
                    )
                )

        return txns


@dataclass(frozen=True)
class BankTxn:
    account_last4: str | None
    trans_date: date
    currency: str
    amount: Decimal
    balance: Decimal | None
    summary: str | None
    counterparty: str | None


def _extract_cmb_account_last4(first_page_text: str) -> str | None:
    # 示例："户 名：张三 账号：6214********9601"
    m = re.search(r"账号：\s*(\S+)", first_page_text)
    if m:
        token = m.group(1).strip()
        tail = re.search(r"(\d{4})$", token)
        if tail:
            return tail.group(1)
    # 兜底：拿到 '账号：' 后面出现的第一个 4 位尾号。
    m = re.search(r"账号：.*?(\d{4})\b", first_page_text)
    if m:
        return m.group(1)
    return None


def extract_cmb_transaction_statement(pdf_path: Path) -> list[BankTxn]:
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}\b")
    footer_re = re.compile(r"^\d+/\d+$")
    ignore_prefixes = (
        "招商银行交易流水",
        "Transaction Statement",
        "户 名：",
        "Name Account",
        "账户类型：",
        "Account Type",
        "申请时间：",
        "Date Verification",
        "记账日期",
        "Transaction",
        "Date Currency",
        "Amount",
    )

    txns: list[BankTxn] = []
    current: BankTxn | None = None
    pending_counterparty: str | None = None

    def has_unclosed_paren(s: str) -> bool:
        return s.count("(") > s.count(")") or s.count("（") > s.count("）")

    def join_counterparty(prefix: str | None, suffix: str | None) -> str | None:
        a = (prefix or "").strip()
        b = (suffix or "").strip()
        if not a and not b:
            return None
        if not a:
            return b
        if not b:
            return a
        if b.startswith((")", "）")):
            return f"{a}{b}"
        return f"{a} {b}"

    def is_counterparty_fragment(s: str) -> bool:
        text = s.strip()
        if not text or len(text) < 4:
            return False
        if date_re.match(text) or footer_re.match(text):
            return False
        # 避免把纯数字/噪声行当成对方户名。
        if re.fullmatch(r"-?\d[\d,]*\.\d{2}", text):
            return False
        # 常见“非商户”独立行（pdfplumber 抽取时偶发）。
        if any(k in text for k in ["记账日期", "交易日期", "Transaction", "Date", "Currency", "Amount", "Balance"]):
            return False
        return True

    def flush() -> None:
        nonlocal current
        if current:
            txns.append(current)
            current = None

    with pdfplumber.open(pdf_path) as pdf:
        first_text = (pdf.pages[0].extract_text() or "").strip()
        account_last4 = _extract_cmb_account_last4(first_text)
        for page in pdf.pages:
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if not line or footer_re.match(line):
                    continue
                if line.startswith(ignore_prefixes):
                    continue

                if date_re.match(line):
                    flush()
                    parts = line.split()
                    if len(parts) < 4:
                        continue
                    d = date.fromisoformat(parts[0])
                    currency = parts[1]
                    amount = _to_decimal(parts[2])
                    balance: Decimal | None = None
                    summary: str | None = None
                    counterparty: str | None = None
                    if len(parts) >= 5:
                        balance = _to_decimal(parts[3])
                        summary = parts[4]
                        counterparty = " ".join(parts[5:]).strip() or None
                    else:
                        balance = _to_decimal(parts[3])

                    if pending_counterparty:
                        if not (counterparty or "").strip() or counterparty.startswith((")", "）")):
                            counterparty = join_counterparty(pending_counterparty, counterparty)
                        pending_counterparty = None

                    current = BankTxn(
                        account_last4=account_last4,
                        trans_date=d,
                        currency=currency,
                        amount=amount,
                        balance=balance,
                        summary=summary,
                        counterparty=counterparty,
                    )
                    continue

                if current:
                    extra = line
                    # 有些 PDF 会把“对方户名”换到下一行（基金类“专户”更常见），但也存在无关的独立行
                    #（例如“鹏华基金管理有限公司销售汇总”“应付利息-...”）。为避免污染对方户名字段，
                    # 只在信号足够强时才把下一行拼接进去：
                    # 1) 当前对方户名为空，或
                    # 2) 当前对方户名括号未闭合，或
                    # 3) 下一行以右括号开头。
                    cur_cp = (current.counterparty or "").strip()
                    if not cur_cp:
                        current = BankTxn(
                            account_last4=current.account_last4,
                            trans_date=current.trans_date,
                            currency=current.currency,
                            amount=current.amount,
                            balance=current.balance,
                            summary=current.summary,
                            counterparty=extra.strip() or None,
                        )
                    elif extra.startswith((")", "）")) or has_unclosed_paren(cur_cp):
                        current = BankTxn(
                            account_last4=current.account_last4,
                            trans_date=current.trans_date,
                            currency=current.currency,
                            amount=current.amount,
                            balance=current.balance,
                            summary=current.summary,
                            counterparty=join_counterparty(cur_cp, extra),
                        )
                    elif is_counterparty_fragment(extra):
                        # pdfplumber 可能重排换行文本块，把对方户名的第一段放到日期行之前；
                        # 这里先暂存，待下一条交易落地时再回填。
                        pending_counterparty = (
                            extra.strip()
                            if not pending_counterparty
                            else f"{pending_counterparty.strip()} {extra.strip()}".strip()
                        )

    flush()
    return txns


@overload
def extract_rows(pdf_path: Path, kind: Literal["cmb_credit_card"]) -> list[CmbCreditCardRow]: ...


@overload
def extract_rows(pdf_path: Path, kind: Literal["cmb_statement"]) -> list[CmbStatementRow]: ...


def extract_rows(pdf_path: Path, kind: CmbKind) -> list[CmbRow]:
    if kind == "cmb_credit_card":
        txns = extract_cmb_credit_card_statement(pdf_path)
        rows: list[CmbCreditCardRow] = []
        for t in txns:
            rows.append(
                {
                    "source": "cmb_credit_card",
                    "section": t.section,
                    "trans_date": t.trans_date.isoformat(),
                    "post_date": t.post_date.isoformat() if t.post_date else "",
                    "description": t.description,
                    "amount_rmb": str(t.amount_rmb),
                    "card_last4": t.card_last4 or "",
                    "original_amount": str(t.original_amount) if t.original_amount is not None else "",
                    "original_region": t.original_region or "",
                }
            )
        return rows

    if kind == "cmb_statement":
        txns = extract_cmb_transaction_statement(pdf_path)
        rows2: list[CmbStatementRow] = []
        for t in txns:
            rows2.append(
                {
                    "source": "cmb_statement",
                    "account_last4": t.account_last4 or "",
                    "trans_date": t.trans_date.isoformat(),
                    "currency": t.currency,
                    "amount": str(t.amount),
                    "balance": str(t.balance) if t.balance is not None else "",
                    "summary": t.summary or "",
                    "counterparty": t.counterparty or "",
                }
            )
        return rows2

    raise ValueError(f"不支持的 PDF kind: {kind}")
