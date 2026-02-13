import csv
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from stages.match_bank import match_bank_statements


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


class TestMatchBankCardAlias(unittest.TestCase):
    def test_debit_card_alias_allows_renewed_card_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bank_csv = root / "bank.csv"
            wechat_csv = root / "wechat.normalized.csv"
            alipay_csv = root / "alipay.normalized.csv"

            _write_csv(
                bank_csv,
                [
                    "source",
                    "account_last4",
                    "trans_date",
                    "currency",
                    "amount",
                    "balance",
                    "summary",
                    "counterparty",
                ],
                [
                    [
                        "cmb_statement",
                        "4101",
                        "2025-01-05",
                        "CNY",
                        "-370.97",
                        "0.00",
                        "快捷支付",
                        "示例对象A",
                    ],
                ],
            )

            _write_csv(
                wechat_csv,
                [
                    "channel",
                    "trans_time",
                    "trans_date",
                    "trans_type",
                    "counterparty",
                    "item",
                    "direction",
                    "amount",
                    "pay_method",
                    "status",
                    "trade_no",
                    "merchant_no",
                    "remark",
                ],
                [],
            )

            _write_csv(
                alipay_csv,
                [
                    "channel",
                    "trans_time",
                    "trans_date",
                    "category",
                    "counterparty",
                    "counterparty_account",
                    "item",
                    "direction",
                    "amount",
                    "pay_method",
                    "status",
                    "trade_no",
                    "merchant_no",
                    "remark",
                ],
                [
                    [
                        "alipay",
                        "2025-01-05 13:06:13",
                        "2025-01-05",
                        "示例分类A",
                        "示例对象A",
                        "sample_a@example.com",
                        "示例消费A",
                        "支出",
                        "370.97",
                        "示例银行储蓄卡(4102)&红包",
                        "交易成功",
                        "trade_demo_001",
                        "merchant_demo_001",
                        "",
                    ],
                ],
            )

            out_no_alias = root / "out_no_alias"
            match_bank_statements(
                bank_csvs=[bank_csv],
                wechat_csv=wechat_csv,
                alipay_csv=alipay_csv,
                out_dir=out_no_alias,
            )
            unmatched_no_alias = _read_csv(out_no_alias / "bank.unmatched.csv")
            self.assertEqual(len(unmatched_no_alias), 1)
            self.assertEqual(unmatched_no_alias.iloc[0]["match_status"], "no_candidate")

            out_with_alias = root / "out_with_alias"
            match_bank_statements(
                bank_csvs=[bank_csv],
                wechat_csv=wechat_csv,
                alipay_csv=alipay_csv,
                out_dir=out_with_alias,
                card_aliases={"4101": ["4102"]},
            )
            enriched_with_alias = _read_csv(out_with_alias / "bank.enriched.csv")
            unmatched_with_alias = _read_csv(out_with_alias / "bank.unmatched.csv")

            self.assertEqual(len(enriched_with_alias), 1)
            self.assertEqual(len(unmatched_with_alias), 0)
            self.assertEqual(enriched_with_alias.iloc[0]["match_status"], "matched")
            self.assertIn("alipay", enriched_with_alias.iloc[0]["match_sources"])

    def test_salary_income_is_not_skipped_as_non_payment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bank_csv = root / "bank.csv"
            wechat_csv = root / "wechat.normalized.csv"
            alipay_csv = root / "alipay.normalized.csv"

            _write_csv(
                bank_csv,
                [
                    "source",
                    "account_last4",
                    "trans_date",
                    "currency",
                    "amount",
                    "balance",
                    "summary",
                    "counterparty",
                ],
                [
                    [
                        "cmb_statement",
                        "4101",
                        "2025-01-27",
                        "CNY",
                        "59657.62",
                        "59657.62",
                        "代发工资",
                        "示例科技有限公司",
                    ],
                ],
            )

            _write_csv(
                wechat_csv,
                [
                    "channel",
                    "trans_time",
                    "trans_date",
                    "trans_type",
                    "counterparty",
                    "item",
                    "direction",
                    "amount",
                    "pay_method",
                    "status",
                    "trade_no",
                    "merchant_no",
                    "remark",
                ],
                [],
            )

            _write_csv(
                alipay_csv,
                [
                    "channel",
                    "trans_time",
                    "trans_date",
                    "category",
                    "counterparty",
                    "counterparty_account",
                    "item",
                    "direction",
                    "amount",
                    "pay_method",
                    "status",
                    "trade_no",
                    "merchant_no",
                    "remark",
                ],
                [],
            )

            out_dir = root / "out"
            match_bank_statements(
                bank_csvs=[bank_csv],
                wechat_csv=wechat_csv,
                alipay_csv=alipay_csv,
                out_dir=out_dir,
            )

            unmatched = _read_csv(out_dir / "bank.unmatched.csv")
            self.assertEqual(len(unmatched), 1)
            self.assertEqual(unmatched.iloc[0]["summary"], "代发工资")
            self.assertEqual(unmatched.iloc[0]["match_status"], "no_candidate")

    def test_bank_rows_no_longer_use_skipped_non_payment_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bank_csv = root / "bank.csv"
            wechat_csv = root / "wechat.normalized.csv"
            alipay_csv = root / "alipay.normalized.csv"

            _write_csv(
                bank_csv,
                [
                    "source",
                    "account_last4",
                    "trans_date",
                    "currency",
                    "amount",
                    "balance",
                    "summary",
                    "counterparty",
                ],
                [
                    [
                        "cmb_statement",
                        "4101",
                        "2025-02-01",
                        "CNY",
                        "5000.00",
                        "5000.00",
                        "转账汇款",
                        "示例对象B",
                    ],
                ],
            )

            _write_csv(
                wechat_csv,
                [
                    "channel",
                    "trans_time",
                    "trans_date",
                    "trans_type",
                    "counterparty",
                    "item",
                    "direction",
                    "amount",
                    "pay_method",
                    "status",
                    "trade_no",
                    "merchant_no",
                    "remark",
                ],
                [],
            )

            _write_csv(
                alipay_csv,
                [
                    "channel",
                    "trans_time",
                    "trans_date",
                    "category",
                    "counterparty",
                    "counterparty_account",
                    "item",
                    "direction",
                    "amount",
                    "pay_method",
                    "status",
                    "trade_no",
                    "merchant_no",
                    "remark",
                ],
                [],
            )

            out_dir = root / "out"
            match_bank_statements(
                bank_csvs=[bank_csv],
                wechat_csv=wechat_csv,
                alipay_csv=alipay_csv,
                out_dir=out_dir,
            )

            unmatched = _read_csv(out_dir / "bank.unmatched.csv")
            self.assertEqual(len(unmatched), 1)
            self.assertEqual(unmatched.iloc[0]["match_status"], "no_candidate")

    def test_duplicate_bank_rows_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bank_csv = root / "bank.csv"
            wechat_csv = root / "wechat.normalized.csv"
            alipay_csv = root / "alipay.normalized.csv"

            _write_csv(
                bank_csv,
                [
                    "source",
                    "account_last4",
                    "trans_date",
                    "currency",
                    "amount",
                    "balance",
                    "summary",
                    "counterparty",
                ],
                [
                    [
                        "cmb_statement",
                        "4101",
                        "2025-12-25",
                        "CNY",
                        "-1328.00",
                        "38421.04",
                        "银联快捷支付",
                        "示例商户B",
                    ],
                    [
                        "cmb_statement",
                        "4101",
                        "2025-12-25",
                        "CNY",
                        "-1328.00",
                        "38421.04",
                        "银联快捷支付",
                        "示例商户B",
                    ],
                ],
            )

            _write_csv(
                wechat_csv,
                [
                    "channel",
                    "trans_time",
                    "trans_date",
                    "trans_type",
                    "counterparty",
                    "item",
                    "direction",
                    "amount",
                    "pay_method",
                    "status",
                    "trade_no",
                    "merchant_no",
                    "remark",
                ],
                [],
            )

            _write_csv(
                alipay_csv,
                [
                    "channel",
                    "trans_time",
                    "trans_date",
                    "category",
                    "counterparty",
                    "counterparty_account",
                    "item",
                    "direction",
                    "amount",
                    "pay_method",
                    "status",
                    "trade_no",
                    "merchant_no",
                    "remark",
                ],
                [],
            )

            out_dir = root / "out"
            match_bank_statements(
                bank_csvs=[bank_csv],
                wechat_csv=wechat_csv,
                alipay_csv=alipay_csv,
                out_dir=out_dir,
            )

            unmatched = _read_csv(out_dir / "bank.unmatched.csv")
            self.assertEqual(len(unmatched), 1)
            self.assertEqual(unmatched.iloc[0]["match_status"], "no_candidate")
