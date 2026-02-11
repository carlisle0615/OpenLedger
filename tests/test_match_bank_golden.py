import tempfile
import unittest
from pathlib import Path

import pandas as pd

from stages.match_bank import match_bank_statements


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "sample_run"
INPUTS_DIR = FIXTURES_DIR / "inputs"
EXPECTED_DIR = FIXTURES_DIR / "expected"


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


class TestMatchBankGolden(unittest.TestCase):
    def test_match_bank_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            match_bank_statements(
                bank_csvs=[INPUTS_DIR / "cmb_statement.transactions.csv"],
                wechat_csv=INPUTS_DIR / "wechat.normalized.csv",
                alipay_csv=INPUTS_DIR / "alipay.normalized.csv",
                out_dir=out_dir,
            )

            got_enriched = _read_csv(out_dir / "bank.enriched.csv")
            exp_enriched = _read_csv(EXPECTED_DIR / "bank.enriched.csv")
            self.assertEqual(got_enriched.columns.tolist(), exp_enriched.columns.tolist())
            self.assertEqual(got_enriched.to_dict("records"), exp_enriched.to_dict("records"))

            got_unmatched = _read_csv(out_dir / "bank.unmatched.csv")
            exp_unmatched = _read_csv(EXPECTED_DIR / "bank.unmatched.csv")
            self.assertEqual(got_unmatched.columns.tolist(), exp_unmatched.columns.tolist())
            self.assertEqual(got_unmatched.to_dict("records"), exp_unmatched.to_dict("records"))
