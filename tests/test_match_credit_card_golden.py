import tempfile
import unittest
from pathlib import Path

import pandas as pd

from stages.match_credit_card import match_credit_card


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "sample_run"
INPUTS_DIR = FIXTURES_DIR / "inputs"
EXPECTED_DIR = FIXTURES_DIR / "expected"


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


class TestMatchCreditCardGolden(unittest.TestCase):
    def test_match_credit_card_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            match_credit_card(
                credit_card_csv=INPUTS_DIR / "cmb_credit_card.transactions.csv",
                wechat_csv=INPUTS_DIR / "wechat.normalized.csv",
                alipay_csv=INPUTS_DIR / "alipay.normalized.csv",
                out_dir=out_dir,
            )

            got_enriched = _read_csv(out_dir / "credit_card.enriched.csv")
            exp_enriched = _read_csv(EXPECTED_DIR / "credit_card.enriched.csv")
            self.assertEqual(got_enriched.columns.tolist(), exp_enriched.columns.tolist())
            self.assertEqual(got_enriched.to_dict("records"), exp_enriched.to_dict("records"))

            got_unmatched = _read_csv(out_dir / "credit_card.unmatched.csv")
            exp_unmatched = _read_csv(EXPECTED_DIR / "credit_card.unmatched.csv")
            self.assertEqual(got_unmatched.columns.tolist(), exp_unmatched.columns.tolist())
            self.assertEqual(got_unmatched.to_dict("records"), exp_unmatched.to_dict("records"))
