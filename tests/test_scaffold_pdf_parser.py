import tempfile
import unittest
from pathlib import Path

from tools.scaffold_pdf_parser import _normalize_id, _normalize_kinds, scaffold


class TestScaffoldPdfParser(unittest.TestCase):
    def test_normalize_id(self) -> None:
        self.assertEqual(_normalize_id("boc", label="mode_id"), "boc")
        self.assertEqual(_normalize_id("boc-parser", label="mode_id"), "boc_parser")
        with self.assertRaises(ValueError):
            _normalize_id("1abc", label="mode_id")

    def test_normalize_kinds_default(self) -> None:
        self.assertEqual(_normalize_kinds("boc", ""), ["boc_statement"])

    def test_scaffold_create_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            result = scaffold(
                root=root,
                mode_id="boc",
                mode_name="中国银行（信用卡/流水）",
                kinds=["boc_credit_card", "boc_statement"],
                force=False,
            )
            self.assertGreaterEqual(len(result["created"]), 7)

            parser_file = root / "openledger" / "parsers" / "pdf" / "boc.py"
            test_file = root / "tests" / "test_pdf_boc_golden.py"
            fixture_file = root / "tests" / "fixtures" / "pdf_parsers" / "boc" / "pdf_text" / "boc_credit_card.txt"
            self.assertTrue(parser_file.exists())
            self.assertTrue(test_file.exists())
            self.assertTrue(fixture_file.exists())
            self.assertIn('MODE_ID: Final[Literal["boc"]]', parser_file.read_text(encoding="utf-8"))

