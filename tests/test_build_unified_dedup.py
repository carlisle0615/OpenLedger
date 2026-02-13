import tempfile
import unittest
from pathlib import Path

import pandas as pd

from openledger.stage_contracts import (
    ART_ALIPAY_NORMALIZED,
    ART_BANK_ENRICHED,
    ART_BANK_UNMATCHED,
    ART_CC_ENRICHED,
    ART_CC_UNMATCHED,
    ART_WECHAT_NORMALIZED,
    required_columns,
)
from stages.build_unified import build_unified


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=columns).fillna("")
    df.to_csv(path, index=False, encoding="utf-8")


class TestBuildUnifiedDedup(unittest.TestCase):
    def test_drop_wallet_row_when_same_match_group_exists_in_bill_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = tmp_path / "output"

            cc_enriched_path = tmp_path / "credit_card.enriched.csv"
            cc_unmatched_path = tmp_path / "credit_card.unmatched.csv"
            bank_enriched_path = tmp_path / "bank.enriched.csv"
            bank_unmatched_path = tmp_path / "bank.unmatched.csv"
            wechat_norm_path = tmp_path / "wechat.normalized.csv"
            alipay_norm_path = tmp_path / "alipay.normalized.csv"

            _write_csv(
                cc_enriched_path,
                required_columns(ART_CC_ENRICHED),
                [
                    {
                        "source": "cmb_credit_card",
                        "section": "消费",
                        "trans_date": "2025-01-21",
                        "post_date": "2025-01-22",
                        "description": "支付宝-示例商户A",
                        "amount_rmb": "3.57",
                        "card_last4": "4101",
                        "original_amount": "3.57",
                        "original_region": "AA",
                        "match_status": "matched",
                        "match_method": "exact",
                        "match_sources": "cmb_credit_card+alipay",
                        "detail_channel": "alipay",
                        "detail_trans_time": "2025-01-21 09:28:54",
                        "detail_trans_date": "2025-01-21",
                        "detail_direction": "支出",
                        "detail_counterparty": "示例商户A",
                        "detail_item": "示例消费场景A",
                        "detail_pay_method": "示例银行信用卡(4101)&红包",
                        "detail_trade_no": "T1",
                        "detail_merchant_no": "M1",
                        "detail_status": "交易成功",
                        "detail_category_or_type": "日用百货",
                        "detail_remark": "",
                        "match_date_diff_days": "0",
                        "match_direction_penalty": "0",
                        "match_text_similarity": "100",
                        "match_confidence": "1",
                    }
                ],
            )

            _write_csv(cc_unmatched_path, required_columns(ART_CC_UNMATCHED), [])
            _write_csv(bank_enriched_path, required_columns(ART_BANK_ENRICHED), [])
            _write_csv(bank_unmatched_path, required_columns(ART_BANK_UNMATCHED), [])
            _write_csv(wechat_norm_path, required_columns(ART_WECHAT_NORMALIZED), [])
            _write_csv(
                alipay_norm_path,
                required_columns(ART_ALIPAY_NORMALIZED),
                [
                    {
                        "channel": "alipay",
                        "trans_time": "2025-01-21 09:28:54",
                        "trans_date": "2025-01-21",
                        "category": "日用百货",
                        "counterparty": "示例商户A",
                        "counterparty_account": "sample_merchant@example.com",
                        "item": "示例消费场景A",
                        "direction": "支出",
                        "amount": "3.57",
                        "pay_method": "示例银行信用卡(4101)&红包",
                        "status": "交易成功",
                        "trade_no": "T1",
                        "merchant_no": "M1",
                        "remark": "",
                    }
                ],
            )

            build_unified(
                cc_enriched_path=cc_enriched_path,
                cc_unmatched_path=cc_unmatched_path,
                bank_enriched_path=bank_enriched_path,
                bank_unmatched_path=bank_unmatched_path,
                wechat_norm_path=wechat_norm_path,
                alipay_norm_path=alipay_norm_path,
                out_dir=out_dir,
            )

            unified = pd.read_csv(out_dir / "unified.transactions.csv", dtype=str).fillna("")
            target = unified[
                (unified["trade_date"] == "2025-01-21")
                & (unified["merchant"] == "示例商户A")
                & (unified["amount"] == "-3.57")
            ]
            self.assertEqual(len(target), 1)
            self.assertEqual(target.iloc[0]["account"], "CMB CreditCard(4101)")
            self.assertEqual(target.iloc[0]["primary_source"], "cmb_credit_card")
            self.assertIn("alipay", target.iloc[0]["sources"])

    def test_bank_salary_flow_is_income(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = tmp_path / "output"

            cc_enriched_path = tmp_path / "credit_card.enriched.csv"
            cc_unmatched_path = tmp_path / "credit_card.unmatched.csv"
            bank_enriched_path = tmp_path / "bank.enriched.csv"
            bank_unmatched_path = tmp_path / "bank.unmatched.csv"
            wechat_norm_path = tmp_path / "wechat.normalized.csv"
            alipay_norm_path = tmp_path / "alipay.normalized.csv"

            _write_csv(cc_enriched_path, required_columns(ART_CC_ENRICHED), [])
            _write_csv(cc_unmatched_path, required_columns(ART_CC_UNMATCHED), [])
            _write_csv(bank_enriched_path, required_columns(ART_BANK_ENRICHED), [])
            _write_csv(
                bank_unmatched_path,
                required_columns(ART_BANK_UNMATCHED),
                [
                    {
                        "source": "cmb_statement",
                        "account_last4": "4101",
                        "trans_date": "2025-01-27",
                        "currency": "CNY",
                        "amount": "59657.62",
                        "balance": "59657.62",
                        "summary": "代发工资",
                        "counterparty": "示例科技有限公司",
                        "match_status": "no_candidate",
                        "match_method": "",
                        "match_confidence": "",
                    }
                ],
            )
            _write_csv(wechat_norm_path, required_columns(ART_WECHAT_NORMALIZED), [])
            _write_csv(alipay_norm_path, required_columns(ART_ALIPAY_NORMALIZED), [])

            build_unified(
                cc_enriched_path=cc_enriched_path,
                cc_unmatched_path=cc_unmatched_path,
                bank_enriched_path=bank_enriched_path,
                bank_unmatched_path=bank_unmatched_path,
                wechat_norm_path=wechat_norm_path,
                alipay_norm_path=alipay_norm_path,
                out_dir=out_dir,
            )

            unified = pd.read_csv(out_dir / "unified.transactions.csv", dtype=str).fillna("")
            self.assertEqual(len(unified), 1)
            self.assertEqual(unified.iloc[0]["flow"], "income")
            self.assertEqual(unified.iloc[0]["amount"], "59657.62")

    def test_wallet_income_keeps_income_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = tmp_path / "output"

            cc_enriched_path = tmp_path / "credit_card.enriched.csv"
            cc_unmatched_path = tmp_path / "credit_card.unmatched.csv"
            bank_enriched_path = tmp_path / "bank.enriched.csv"
            bank_unmatched_path = tmp_path / "bank.unmatched.csv"
            wechat_norm_path = tmp_path / "wechat.normalized.csv"
            alipay_norm_path = tmp_path / "alipay.normalized.csv"

            _write_csv(cc_enriched_path, required_columns(ART_CC_ENRICHED), [])
            _write_csv(cc_unmatched_path, required_columns(ART_CC_UNMATCHED), [])
            _write_csv(bank_enriched_path, required_columns(ART_BANK_ENRICHED), [])
            _write_csv(bank_unmatched_path, required_columns(ART_BANK_UNMATCHED), [])
            _write_csv(wechat_norm_path, required_columns(ART_WECHAT_NORMALIZED), [])
            _write_csv(
                alipay_norm_path,
                required_columns(ART_ALIPAY_NORMALIZED),
                [
                    {
                        "channel": "alipay",
                        "trans_time": "2025-01-27 11:24:09",
                        "trans_date": "2025-01-27",
                        "category": "转账",
                        "counterparty": "示例科技有限公司",
                        "counterparty_account": "sample_income@example.com",
                        "item": "工资发放",
                        "direction": "收入",
                        "amount": "500.00",
                        "pay_method": "",
                        "status": "交易成功",
                        "trade_no": "trade_income_001",
                        "merchant_no": "merchant_income_001",
                        "remark": "",
                    }
                ],
            )

            build_unified(
                cc_enriched_path=cc_enriched_path,
                cc_unmatched_path=cc_unmatched_path,
                bank_enriched_path=bank_enriched_path,
                bank_unmatched_path=bank_unmatched_path,
                wechat_norm_path=wechat_norm_path,
                alipay_norm_path=alipay_norm_path,
                out_dir=out_dir,
            )

            unified = pd.read_csv(out_dir / "unified.transactions.csv", dtype=str).fillna("")
            self.assertEqual(len(unified), 1)
            self.assertEqual(unified.iloc[0]["flow"], "income")
            self.assertEqual(unified.iloc[0]["amount"], "500.00")

    def test_drop_wallet_row_when_merchant_no_reused_across_periods(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = tmp_path / "output"

            cc_enriched_path = tmp_path / "credit_card.enriched.csv"
            cc_unmatched_path = tmp_path / "credit_card.unmatched.csv"
            bank_enriched_path = tmp_path / "bank.enriched.csv"
            bank_unmatched_path = tmp_path / "bank.unmatched.csv"
            wechat_norm_path = tmp_path / "wechat.normalized.csv"
            alipay_norm_path = tmp_path / "alipay.normalized.csv"

            _write_csv(cc_enriched_path, required_columns(ART_CC_ENRICHED), [])
            _write_csv(cc_unmatched_path, required_columns(ART_CC_UNMATCHED), [])
            _write_csv(
                bank_enriched_path,
                required_columns(ART_BANK_ENRICHED),
                [
                    {
                        "source": "cmb_statement",
                        "account_last4": "4103",
                        "trans_date": "2025-09-03",
                        "currency": "CNY",
                        "amount": "-336.95",
                        "summary": "快捷支付",
                        "counterparty": "余杭供电局",
                        "match_status": "matched",
                        "match_sources": "cmb_statement(4103)+alipay",
                        "detail_channel": "alipay",
                        "detail_trans_time": "2025-09-03 14:18:04",
                        "detail_trans_date": "2025-09-03",
                        "detail_direction": "支出",
                        "detail_counterparty": "余杭供电局",
                        "detail_item": "电费",
                        "detail_pay_method": "招商银行储蓄卡(4103)",
                        "detail_trade_no": "trade_old",
                        "detail_merchant_no": "merchant_shared",
                        "detail_status": "交易成功",
                        "detail_category_or_type": "生活缴费",
                        "detail_remark": "",
                        "match_date_diff_days": "0",
                        "match_direction_penalty": "0",
                        "match_text_similarity": "100",
                        "match_confidence": "1",
                    },
                    {
                        "source": "cmb_statement",
                        "account_last4": "4103",
                        "trans_date": "2025-10-02",
                        "currency": "CNY",
                        "amount": "-279.91",
                        "summary": "快捷支付",
                        "counterparty": "余杭供电局",
                        "match_status": "matched",
                        "match_sources": "cmb_statement(4103)+alipay",
                        "detail_channel": "alipay",
                        "detail_trans_time": "2025-10-02 11:06:25",
                        "detail_trans_date": "2025-10-02",
                        "detail_direction": "支出",
                        "detail_counterparty": "余杭供电局",
                        "detail_item": "电费",
                        "detail_pay_method": "招商银行储蓄卡(4103)",
                        "detail_trade_no": "trade_new",
                        "detail_merchant_no": "merchant_shared",
                        "detail_status": "交易成功",
                        "detail_category_or_type": "生活缴费",
                        "detail_remark": "",
                        "match_date_diff_days": "0",
                        "match_direction_penalty": "0",
                        "match_text_similarity": "100",
                        "match_confidence": "1",
                    },
                ],
            )
            _write_csv(bank_unmatched_path, required_columns(ART_BANK_UNMATCHED), [])
            _write_csv(wechat_norm_path, required_columns(ART_WECHAT_NORMALIZED), [])
            _write_csv(
                alipay_norm_path,
                required_columns(ART_ALIPAY_NORMALIZED),
                [
                    {
                        "channel": "alipay",
                        "trans_time": "2025-10-02 11:06:25",
                        "trans_date": "2025-10-02",
                        "category": "生活缴费",
                        "counterparty": "余杭供电局",
                        "counterparty_account": "power@example.com",
                        "item": "电费",
                        "direction": "支出",
                        "amount": "279.91",
                        "pay_method": "招商银行储蓄卡(4103)",
                        "status": "交易成功",
                        "trade_no": "trade_new",
                        "merchant_no": "merchant_shared",
                        "remark": "",
                    }
                ],
            )

            build_unified(
                cc_enriched_path=cc_enriched_path,
                cc_unmatched_path=cc_unmatched_path,
                bank_enriched_path=bank_enriched_path,
                bank_unmatched_path=bank_unmatched_path,
                wechat_norm_path=wechat_norm_path,
                alipay_norm_path=alipay_norm_path,
                out_dir=out_dir,
            )

            unified = pd.read_csv(out_dir / "unified.transactions.csv", dtype=str).fillna("")
            target = unified[
                (unified["trade_date"] == "2025-10-02")
                & (unified["merchant"] == "余杭供电局")
                & (unified["amount"] == "-279.91")
            ]
            self.assertEqual(len(target), 1)
            self.assertEqual(target.iloc[0]["primary_source"], "cmb_statement")

    def test_bank_housing_fund_inflow_is_income(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = tmp_path / "output"

            cc_enriched_path = tmp_path / "credit_card.enriched.csv"
            cc_unmatched_path = tmp_path / "credit_card.unmatched.csv"
            bank_enriched_path = tmp_path / "bank.enriched.csv"
            bank_unmatched_path = tmp_path / "bank.unmatched.csv"
            wechat_norm_path = tmp_path / "wechat.normalized.csv"
            alipay_norm_path = tmp_path / "alipay.normalized.csv"

            _write_csv(cc_enriched_path, required_columns(ART_CC_ENRICHED), [])
            _write_csv(cc_unmatched_path, required_columns(ART_CC_UNMATCHED), [])
            _write_csv(bank_enriched_path, required_columns(ART_BANK_ENRICHED), [])
            _write_csv(
                bank_unmatched_path,
                required_columns(ART_BANK_UNMATCHED),
                [
                    {
                        "source": "cmb_statement",
                        "account_last4": "4103",
                        "trans_date": "2025-11-04",
                        "currency": "CNY",
                        "amount": "9765.00",
                        "balance": "10000.00",
                        "summary": "转账汇款",
                        "counterparty": "某省住房公积金管理中心",
                        "match_status": "no_candidate",
                    }
                ],
            )
            _write_csv(wechat_norm_path, required_columns(ART_WECHAT_NORMALIZED), [])
            _write_csv(alipay_norm_path, required_columns(ART_ALIPAY_NORMALIZED), [])

            build_unified(
                cc_enriched_path=cc_enriched_path,
                cc_unmatched_path=cc_unmatched_path,
                bank_enriched_path=bank_enriched_path,
                bank_unmatched_path=bank_unmatched_path,
                wechat_norm_path=wechat_norm_path,
                alipay_norm_path=alipay_norm_path,
                out_dir=out_dir,
            )

            unified = pd.read_csv(out_dir / "unified.transactions.csv", dtype=str).fillna("")
            self.assertEqual(len(unified), 1)
            self.assertEqual(unified.iloc[0]["flow"], "income")
            self.assertEqual(unified.iloc[0]["amount"], "9765.00")

    def test_bank_huang_wei_positive_transfer_is_income(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = tmp_path / "output"

            cc_enriched_path = tmp_path / "credit_card.enriched.csv"
            cc_unmatched_path = tmp_path / "credit_card.unmatched.csv"
            bank_enriched_path = tmp_path / "bank.enriched.csv"
            bank_unmatched_path = tmp_path / "bank.unmatched.csv"
            wechat_norm_path = tmp_path / "wechat.normalized.csv"
            alipay_norm_path = tmp_path / "alipay.normalized.csv"

            _write_csv(cc_enriched_path, required_columns(ART_CC_ENRICHED), [])
            _write_csv(cc_unmatched_path, required_columns(ART_CC_UNMATCHED), [])
            _write_csv(bank_enriched_path, required_columns(ART_BANK_ENRICHED), [])
            _write_csv(
                bank_unmatched_path,
                required_columns(ART_BANK_UNMATCHED),
                [
                    {
                        "source": "cmb_statement",
                        "account_last4": "4103",
                        "trans_date": "2025-12-05",
                        "currency": "CNY",
                        "amount": "5000.00",
                        "balance": "12000.00",
                        "summary": "转账汇款",
                        "counterparty": "sample_extra_income_user",
                        "match_status": "no_candidate",
                    }
                ],
            )
            _write_csv(wechat_norm_path, required_columns(ART_WECHAT_NORMALIZED), [])
            _write_csv(alipay_norm_path, required_columns(ART_ALIPAY_NORMALIZED), [])

            build_unified(
                cc_enriched_path=cc_enriched_path,
                cc_unmatched_path=cc_unmatched_path,
                bank_enriched_path=bank_enriched_path,
                bank_unmatched_path=bank_unmatched_path,
                wechat_norm_path=wechat_norm_path,
                alipay_norm_path=alipay_norm_path,
                out_dir=out_dir,
            )

            unified = pd.read_csv(out_dir / "unified.transactions.csv", dtype=str).fillna("")
            self.assertEqual(len(unified), 1)
            self.assertEqual(unified.iloc[0]["flow"], "income")
            self.assertEqual(unified.iloc[0]["amount"], "5000.00")
