import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from stages.finalize import finalize


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8")


class TestFinalizeAutoDedup(unittest.TestCase):
    def test_auto_ignore_wallet_duplicate_in_same_match_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "classifier.json"
            unified_path = tmp_path / "unified.with_id.csv"
            review_path = tmp_path / "review.csv"
            out_dir = tmp_path / "output"

            config_path.write_text(
                json.dumps(
                    {
                        "categories": [
                            {"id": "dining", "name": "餐饮"},
                            {"id": "other", "name": "其他"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            _write_csv(
                unified_path,
                [
                    {
                        "txn_id": "bill_1",
                        "trade_date": "2025-01-20",
                        "amount": "-12.00",
                        "flow": "expense",
                        "merchant": "示例商户",
                        "item": "示例商品",
                        "primary_source": "cmb_credit_card",
                        "match_group_id": "mg_same",
                    },
                    {
                        "txn_id": "wallet_1",
                        "trade_date": "2025-01-20",
                        "amount": "-12.00",
                        "flow": "expense",
                        "merchant": "示例商户",
                        "item": "示例商品",
                        "primary_source": "alipay",
                        "match_group_id": "mg_same",
                    },
                    {
                        "txn_id": "extra_1",
                        "trade_date": "2025-01-21",
                        "amount": "-20.00",
                        "flow": "expense",
                        "merchant": "示例商户B",
                        "item": "示例商品B",
                        "primary_source": "alipay",
                        "match_group_id": "",
                    },
                ],
            )

            _write_csv(
                review_path,
                [
                    {
                        "txn_id": "bill_1",
                        "suggested_category_id": "dining",
                        "suggested_uncertain": "false",
                        "suggested_confidence": "1",
                        "suggested_note": "rule",
                        "final_category_id": "",
                        "final_note": "",
                    },
                    {
                        "txn_id": "wallet_1",
                        "suggested_category_id": "dining",
                        "suggested_uncertain": "false",
                        "suggested_confidence": "1",
                        "suggested_note": "rule",
                        "final_category_id": "",
                        "final_note": "",
                    },
                    {
                        "txn_id": "extra_1",
                        "suggested_category_id": "dining",
                        "suggested_uncertain": "false",
                        "suggested_confidence": "1",
                        "suggested_note": "rule",
                        "final_category_id": "",
                        "final_note": "",
                    },
                ],
            )

            finalize(
                config_path=config_path,
                unified_with_id_csv=unified_path,
                review_csv=review_path,
                out_dir=out_dir,
                drop_cols=[],
                require_review=False,
            )

            detailed = pd.read_csv(out_dir / "unified.transactions.categorized.csv", dtype=str).fillna("")
            summary = pd.read_csv(out_dir / "category.summary.csv", dtype=str).fillna("")

            wallet_row = detailed[detailed["txn_id"] == "wallet_1"].iloc[0]
            self.assertEqual(wallet_row["ignored"], "true")
            self.assertIn("自动去重", wallet_row["ignore_reason"])

            bill_row = detailed[detailed["txn_id"] == "bill_1"].iloc[0]
            self.assertEqual(bill_row["ignored"], "false")

            dining_row = summary[summary["category_id"] == "dining"].iloc[0]
            self.assertEqual(dining_row["sum_expense"], "-32.0")

    def test_dedupe_same_txn_id_avoids_merge_fanout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "classifier.json"
            unified_path = tmp_path / "unified.with_id.csv"
            review_path = tmp_path / "review.csv"
            out_dir = tmp_path / "output"

            config_path.write_text(
                json.dumps(
                    {
                        "categories": [
                            {"id": "red_packet_transfer", "name": "红包转账"},
                            {"id": "other", "name": "其他"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            # unified 与 review 都有重复 txn_id；finalize 应去重并避免笛卡尔放大。
            _write_csv(
                unified_path,
                [
                    {
                        "txn_id": "dup_1",
                        "trade_date": "2025-01-26",
                        "amount": "-2.00",
                        "flow": "expense",
                        "merchant": "微信红包",
                        "item": "",
                        "primary_source": "cmb_statement",
                        "match_group_id": "",
                    },
                    {
                        "txn_id": "dup_1",
                        "trade_date": "2025-01-26",
                        "amount": "-2.00",
                        "flow": "expense",
                        "merchant": "微信红包",
                        "item": "",
                        "primary_source": "cmb_statement",
                        "match_group_id": "",
                    },
                    {
                        "txn_id": "single_1",
                        "trade_date": "2025-01-27",
                        "amount": "-1.00",
                        "flow": "expense",
                        "merchant": "微信红包",
                        "item": "",
                        "primary_source": "cmb_statement",
                        "match_group_id": "",
                    },
                ],
            )

            _write_csv(
                review_path,
                [
                    {
                        "txn_id": "dup_1",
                        "suggested_category_id": "red_packet_transfer",
                        "suggested_uncertain": "false",
                        "suggested_confidence": "1",
                        "suggested_note": "rule",
                        "final_category_id": "",
                        "final_note": "",
                    },
                    {
                        "txn_id": "dup_1",
                        "suggested_category_id": "red_packet_transfer",
                        "suggested_uncertain": "false",
                        "suggested_confidence": "1",
                        "suggested_note": "rule",
                        "final_category_id": "",
                        "final_note": "",
                    },
                    {
                        "txn_id": "single_1",
                        "suggested_category_id": "red_packet_transfer",
                        "suggested_uncertain": "false",
                        "suggested_confidence": "1",
                        "suggested_note": "rule",
                        "final_category_id": "",
                        "final_note": "",
                    },
                ],
            )

            finalize(
                config_path=config_path,
                unified_with_id_csv=unified_path,
                review_csv=review_path,
                out_dir=out_dir,
                drop_cols=[],
                require_review=False,
            )

            detailed = pd.read_csv(out_dir / "unified.transactions.categorized.csv", dtype=str).fillna("")
            summary = pd.read_csv(out_dir / "category.summary.csv", dtype=str).fillna("")

            # 只应保留 2 行（dup_1 1 行 + single_1 1 行）
            self.assertEqual(len(detailed), 2)
            self.assertEqual((detailed["txn_id"] == "dup_1").sum(), 1)

            rp_row = summary[summary["category_id"] == "red_packet_transfer"].iloc[0]
            self.assertEqual(rp_row["sum_expense"], "-3.0")

    def test_normalize_flow_and_auto_ignore_missing_amount(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "classifier.json"
            unified_path = tmp_path / "unified.with_id.csv"
            review_path = tmp_path / "review.csv"
            out_dir = tmp_path / "output"

            config_path.write_text(
                json.dumps(
                    {
                        "categories": [
                            {"id": "refund", "name": "退款"},
                            {"id": "other", "name": "其他"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            _write_csv(
                unified_path,
                [
                    {
                        "txn_id": "refund_like_1",
                        "trade_date": "2025-01-22",
                        "amount": "624.43",
                        "flow": "银联代付",
                        "merchant": "清算帐户",
                        "item": "",
                        "primary_source": "cmb_statement",
                        "match_group_id": "",
                    },
                    {
                        "txn_id": "missing_amount_1",
                        "trade_date": "2025-02-04",
                        "amount": "",
                        "flow": "other",
                        "merchant": "招商银行",
                        "item": "提现-实时提现",
                        "primary_source": "alipay",
                        "match_group_id": "",
                    },
                ],
            )

            _write_csv(
                review_path,
                [
                    {
                        "txn_id": "refund_like_1",
                        "suggested_category_id": "refund",
                        "suggested_uncertain": "false",
                        "suggested_confidence": "1",
                        "suggested_note": "rule",
                        "final_category_id": "",
                        "final_note": "",
                    },
                    {
                        "txn_id": "missing_amount_1",
                        "suggested_category_id": "other",
                        "suggested_uncertain": "false",
                        "suggested_confidence": "1",
                        "suggested_note": "rule",
                        "final_category_id": "",
                        "final_note": "",
                    },
                ],
            )

            finalize(
                config_path=config_path,
                unified_with_id_csv=unified_path,
                review_csv=review_path,
                out_dir=out_dir,
                drop_cols=[],
                require_review=False,
            )

            detailed = pd.read_csv(out_dir / "unified.transactions.categorized.csv", dtype=str).fillna("")
            summary = pd.read_csv(out_dir / "category.summary.csv", dtype=str).fillna("")

            refund_row = detailed[detailed["txn_id"] == "refund_like_1"].iloc[0]
            self.assertEqual(refund_row["flow"], "refund")
            self.assertEqual(refund_row["ignored"], "false")

            missing_row = detailed[detailed["txn_id"] == "missing_amount_1"].iloc[0]
            self.assertEqual(missing_row["ignored"], "true")
            self.assertIn("金额缺失", missing_row["ignore_reason"])

            sum_refund = summary[summary["category_id"] == "refund"].iloc[0]["sum_refund"]
            self.assertEqual(sum_refund, "624.43")

    def test_auto_ignore_shadow_wallet_duplicate_without_same_match_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "classifier.json"
            unified_path = tmp_path / "unified.with_id.csv"
            review_path = tmp_path / "review.csv"
            out_dir = tmp_path / "output"

            config_path.write_text(
                json.dumps(
                    {
                        "categories": [
                            {"id": "utilities", "name": "生活缴费"},
                            {"id": "other", "name": "其他"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            _write_csv(
                unified_path,
                [
                    {
                        "txn_id": "wallet_shadow",
                        "trade_date": "2025-10-02",
                        "trade_time": "2025-10-02 11:06:25",
                        "amount": "-279.91",
                        "flow": "expense",
                        "merchant": "余杭供电局",
                        "item": "电费",
                        "primary_source": "alipay",
                        "sources": "alipay",
                        "match_status": "",
                        "match_group_id": "mg_old",
                        "remark": "匹配到账单：CMB Debit(4103) 2025-10-02 -279.91 快捷支付",
                    },
                    {
                        "txn_id": "bill_kept",
                        "trade_date": "2025-10-02",
                        "trade_time": "2025-10-02 11:06:25",
                        "amount": "-279.91",
                        "flow": "expense",
                        "merchant": "余杭供电局",
                        "item": "电费",
                        "primary_source": "cmb_statement",
                        "sources": "cmb_statement|alipay",
                        "match_status": "matched",
                        "match_group_id": "mg_new",
                        "remark": "多源匹配：cmb_statement(4103)+alipay",
                    },
                ],
            )

            _write_csv(
                review_path,
                [
                    {
                        "txn_id": "wallet_shadow",
                        "suggested_category_id": "utilities",
                        "suggested_uncertain": "false",
                        "suggested_confidence": "1",
                        "suggested_note": "rule",
                        "final_category_id": "",
                        "final_note": "",
                    },
                    {
                        "txn_id": "bill_kept",
                        "suggested_category_id": "utilities",
                        "suggested_uncertain": "false",
                        "suggested_confidence": "1",
                        "suggested_note": "rule",
                        "final_category_id": "",
                        "final_note": "",
                    },
                ],
            )

            finalize(
                config_path=config_path,
                unified_with_id_csv=unified_path,
                review_csv=review_path,
                out_dir=out_dir,
                drop_cols=[],
                require_review=False,
            )

            detailed = pd.read_csv(out_dir / "unified.transactions.categorized.csv", dtype=str).fillna("")
            wallet_row = detailed[detailed["txn_id"] == "wallet_shadow"].iloc[0]
            bill_row = detailed[detailed["txn_id"] == "bill_kept"].iloc[0]
            self.assertEqual(wallet_row["ignored"], "true")
            self.assertIn("影子重复", wallet_row["ignore_reason"])
            self.assertEqual(bill_row["ignored"], "false")


if __name__ == "__main__":
    unittest.main()
