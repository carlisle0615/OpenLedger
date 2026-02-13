import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from openledger.profiles import (
    add_bill_from_run,
    create_profile,
    get_run_binding,
    load_profile,
    set_run_binding,
)


def _write_run(root: Path, run_id: str, *, year: int, month: int, profile_id: str = "") -> None:
    run_dir = root / "runs" / run_id
    out_dir = run_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "run_id": run_id,
        "created_at": "2026-01-01T00:00:00+00:00",
        "options": {
            "period_mode": "billing",
            "period_day": 20,
            "period_year": year,
            "period_month": month,
            "profile_id": profile_id,
        },
    }
    (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    (out_dir / "category.summary.csv").write_text(
        "category_id,category_name,count,sum_amount,sum_expense,sum_income,sum_refund,sum_transfer\n"
        "food,餐饮,1,100,100,0,0,0\n",
        encoding="utf-8",
    )
    (out_dir / "unified.transactions.categorized.csv").write_text(
        "txn_id,trade_date,amount,final_category_id\n"
        "t1,2026-01-01,100,food\n",
        encoding="utf-8",
    )


class ProfileBindingTests(unittest.TestCase):
    def test_bill_metrics_recomputed_from_outputs_each_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = create_profile(root, "Alice")
            _write_run(root, "run_a", year=2026, month=1)

            add_bill_from_run(root, profile["id"], "run_a")

            loaded_1 = load_profile(root, profile["id"])
            self.assertEqual(len(loaded_1["bills"]), 1)
            self.assertAlmostEqual(float(loaded_1["bills"][0]["totals"]["sum_amount"]), 100.0, places=4)

            categorized_path = root / "runs" / "run_a" / "output" / "unified.transactions.categorized.csv"
            categorized_path.write_text(
                "txn_id,trade_date,amount,category_id,category_name,ignored,flow\n"
                "t1,2026-01-01,250,food,餐饮,false,expense\n",
                encoding="utf-8",
            )

            loaded_2 = load_profile(root, profile["id"])
            self.assertAlmostEqual(float(loaded_2["bills"][0]["totals"]["sum_amount"]), 250.0, places=4)

            db = root / "profiles.db"
            with sqlite3.connect(db) as conn:
                row = conn.execute(
                    "SELECT totals_json, category_summary_json FROM bills WHERE profile_id = ? AND run_id = ?",
                    (profile["id"], "run_a"),
                ).fetchone()
            self.assertIsNotNone(row)
            assert row is not None
            self.assertIsNone(row[0])
            self.assertIsNone(row[1])

    def test_bind_without_month_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = create_profile(root, "Alice")
            _write_run(root, "run_a", year=2026, month=1)

            add_bill_from_run(
                root,
                profile["id"],
                "run_a",
                period_year=None,
                period_month=None,
            )

            loaded = load_profile(root, profile["id"])
            self.assertEqual(len(loaded["bills"]), 1)
            self.assertIsNone(loaded["bills"][0]["year"])
            self.assertIsNone(loaded["bills"][0]["month"])
            self.assertEqual(loaded["bills"][0]["period_key"], "")

    def test_same_year_month_cannot_bind_two_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = create_profile(root, "Alice")
            _write_run(root, "run_a", year=2026, month=1)
            _write_run(root, "run_b", year=2026, month=2)

            add_bill_from_run(
                root,
                profile["id"],
                "run_a",
                period_year=2026,
                period_month=3,
            )
            with self.assertRaises(ValueError) as ctx:
                add_bill_from_run(
                    root,
                    profile["id"],
                    "run_b",
                    period_year=2026,
                    period_month=3,
                )
            self.assertIn("同月不能绑定多个 run", str(ctx.exception))

    def test_partial_year_month_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = create_profile(root, "Alice")
            _write_run(root, "run_a", year=2026, month=1)
            with self.assertRaises(ValueError):
                add_bill_from_run(
                    root,
                    profile["id"],
                    "run_a",
                    period_year=2026,
                    period_month=None,
                )

    def test_set_and_get_run_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = create_profile(root, "Alice")
            _write_run(root, "run_a", year=2026, month=1)
            binding = set_run_binding(root, "run_a", profile["id"])
            self.assertEqual(binding["profile_id"], profile["id"])
            loaded = get_run_binding(root, "run_a")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["profile_id"], profile["id"])

    def test_set_run_binding_conflicts_with_existing_bill_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alice = create_profile(root, "Alice")
            bob = create_profile(root, "Bob")
            _write_run(root, "run_a", year=2026, month=1)
            add_bill_from_run(root, alice["id"], "run_a")
            with self.assertRaises(ValueError):
                set_run_binding(root, "run_a", bob["id"])

    def test_add_bill_respects_existing_run_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alice = create_profile(root, "Alice")
            bob = create_profile(root, "Bob")
            _write_run(root, "run_a", year=2026, month=1)
            set_run_binding(root, "run_a", alice["id"])
            with self.assertRaises(ValueError):
                add_bill_from_run(root, bob["id"], "run_a")

    def test_get_run_binding_backfills_from_legacy_state_profile_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alice = create_profile(root, "Alice")
            _write_run(root, "run_a", year=2026, month=1, profile_id=alice["id"])
            loaded = get_run_binding(root, "run_a")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["profile_id"], alice["id"])
            db = root / "profiles.db"
            with sqlite3.connect(db) as conn:
                row = conn.execute(
                    "SELECT profile_id FROM run_bindings WHERE run_id = ?",
                    ("run_a",),
                ).fetchone()
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(str(row[0]), alice["id"])


if __name__ == "__main__":
    unittest.main()
