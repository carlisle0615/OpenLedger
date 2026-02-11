import tempfile
import unittest
from pathlib import Path

import pandas as pd

from stages.build_unified import build_unified


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "sample_run"
INPUTS_DIR = FIXTURES_DIR / "inputs"
EXPECTED_DIR = FIXTURES_DIR / "expected"


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


class TestBuildUnifiedGolden(unittest.TestCase):
    def test_build_unified_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            build_unified(
                cc_enriched_path=EXPECTED_DIR / "credit_card.enriched.csv",
                cc_unmatched_path=EXPECTED_DIR / "credit_card.unmatched.csv",
                bank_enriched_path=EXPECTED_DIR / "bank.enriched.csv",
                bank_unmatched_path=EXPECTED_DIR / "bank.unmatched.csv",
                wechat_norm_path=INPUTS_DIR / "wechat.normalized.csv",
                alipay_norm_path=INPUTS_DIR / "alipay.normalized.csv",
                out_dir=out_dir,
            )

            got = _read_csv(out_dir / "unified.transactions.csv")
            exp = _read_csv(EXPECTED_DIR / "unified.transactions.csv")
            self.assertEqual(got.columns.tolist(), exp.columns.tolist())
            self.assertEqual(got.to_dict("records"), exp.to_dict("records"))
