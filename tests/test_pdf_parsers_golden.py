import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from openledger.parsers.pdf.cmb import extract_rows


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "sample_run"
PDF_TEXT_DIR = FIXTURES_DIR / "pdf_text"
EXPECTED_PDF_DIR = FIXTURES_DIR / "expected_pdf"


def _read_csv(path: Path) -> list[dict]:
    df = pd.read_csv(path, dtype=str).fillna("")
    return df.to_dict("records")


def _read_pages(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [p.strip("\n") for p in text.split("\n\n---PAGE---\n\n") if p.strip()]


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


class TestPdfParsersGolden(unittest.TestCase):
    def test_cmb_credit_card_parser(self) -> None:
        pages = _read_pages(PDF_TEXT_DIR / "cmb_credit_card.txt")
        expected = _read_csv(EXPECTED_PDF_DIR / "cmb_credit_card.txt.csv")
        with patch("openledger.parsers.pdf.cmb.pdfplumber.open", return_value=_FakePdf(pages)):
            rows = extract_rows(Path("dummy.pdf"), "cmb_credit_card")
        self.assertEqual(rows, expected)

    def test_cmb_statement_parser(self) -> None:
        pages = _read_pages(PDF_TEXT_DIR / "cmb_statement.txt")
        expected = _read_csv(EXPECTED_PDF_DIR / "cmb_statement.txt.csv")
        with patch("openledger.parsers.pdf.cmb.pdfplumber.open", return_value=_FakePdf(pages)):
            rows = extract_rows(Path("dummy.pdf"), "cmb_statement")
        self.assertEqual(rows, expected)
