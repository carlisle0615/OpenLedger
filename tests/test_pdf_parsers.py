import tempfile
import unittest
from pathlib import Path

from openledger.parsers.pdf import list_pdf_modes
from openledger.parsers.pdf.cmb import detect_kind_from_text
from openledger.state import init_run_state
from openledger.infrastructure.workflow.runtime import get_state, make_paths, save_state


class TestPdfParserRegistry(unittest.TestCase):
    def test_list_pdf_modes_contains_auto_and_cmb(self) -> None:
        modes = list_pdf_modes()
        ids = {m.get("id") for m in modes}
        self.assertIn("auto", ids)
        self.assertIn("cmb", ids)


class TestCmbDetectKind(unittest.TestCase):
    def test_detect_credit_card(self) -> None:
        text = "招商银行信用卡对账单\n账单日 2024年06月20日"
        self.assertEqual(detect_kind_from_text(text), "cmb_credit_card")

    def test_detect_statement(self) -> None:
        text = "Transaction Statement of China Merchants Bank\n招商银行交易流水"
        self.assertEqual(detect_kind_from_text(text), "cmb_statement")


class TestPdfModeDefault(unittest.TestCase):
    def test_init_run_state_has_pdf_mode(self) -> None:
        st = init_run_state("run_x")
        self.assertEqual(st["options"]["pdf_mode"], "auto")

    def test_get_state_sets_default_pdf_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_id = "run_1"
            paths = make_paths(root, run_id)
            paths.run_dir.mkdir(parents=True, exist_ok=True)

            st = init_run_state(run_id)
            # 模拟旧版本 state.json：缺少 pdf_mode
            st["options"].pop("pdf_mode", None)
            save_state(paths, st)

            loaded = get_state(paths)
            self.assertEqual(loaded["options"]["pdf_mode"], "auto")
