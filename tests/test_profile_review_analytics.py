import json
import tempfile
import unittest
from pathlib import Path

from openledger.profile_review import build_profile_review
from openledger.profiles import add_bill_from_run, create_profile
from openledger.server import create_app

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - 测试环境可能缺少 httpx
    TestClient = None


def _split_amount(total: float, parts: int) -> list[float]:
    if parts <= 0:
        return []
    cents = int(round(abs(total) * 100))
    base = cents // parts
    remainder = cents % parts
    values: list[float] = []
    for idx in range(parts):
        piece = base + (1 if idx < remainder else 0)
        values.append(piece / 100.0)
    return values


def _write_run(
    root: Path,
    run_id: str,
    *,
    year: int | None,
    month: int | None,
    categories: list[tuple[str, str, int, float, float]],
) -> None:
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
        },
    }
    (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    summary_lines = [
        "category_id,category_name,count,sum_amount,sum_expense,sum_income,sum_refund,sum_transfer"
    ]
    categorized_lines = ["txn_id,trade_date,amount,category_id,category_name,ignored,flow"]
    row_idx = 0
    trade_date = f"{year or 2026:04d}-{month or 1:02d}-01"
    for category_id, category_name, count, expense, income in categories:
        exp = abs(float(expense))
        inc = abs(float(income))
        sum_expense = -exp
        sum_income = inc
        sum_amount = sum_income + sum_expense
        summary_lines.append(
            f"{category_id},{category_name},{int(count)},{sum_amount:.2f},{sum_expense:.2f},{sum_income:.2f},0,0"
        )
        row_count = int(count)
        if row_count <= 0:
            continue
        if exp > 0 and inc <= 0:
            pieces = _split_amount(exp, row_count)
            for piece in pieces:
                row_idx += 1
                categorized_lines.append(
                    f"{run_id}_{row_idx},{trade_date},{-piece:.2f},{category_id},{category_name},false,expense"
                )
        elif inc > 0 and exp <= 0:
            pieces = _split_amount(inc, row_count)
            for piece in pieces:
                row_idx += 1
                categorized_lines.append(
                    f"{run_id}_{row_idx},{trade_date},{piece:.2f},{category_id},{category_name},false,income"
                )
        else:
            net = inc - exp
            pieces = _split_amount(abs(net), row_count)
            flow = "income" if net >= 0 else "expense"
            sign = 1.0 if net >= 0 else -1.0
            for piece in pieces:
                row_idx += 1
                categorized_lines.append(
                    f"{run_id}_{row_idx},{trade_date},{sign * piece:.2f},{category_id},{category_name},false,{flow}"
                )
    (out_dir / "category.summary.csv").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    (out_dir / "unified.transactions.categorized.csv").write_text(
        "\n".join(categorized_lines) + "\n",
        encoding="utf-8",
    )


def _prepare_profile(root: Path) -> str:
    profile = create_profile(root, "Alice")
    profile_id = str(profile["id"])

    _write_run(
        root,
        "run_202501",
        year=2025,
        month=1,
        categories=[
            ("dining", "餐饮", 6, 480.0, 0.0),
            ("other", "其他", 4, 320.0, 0.0),
        ],
    )
    _write_run(
        root,
        "run_202601",
        year=2026,
        month=1,
        categories=[
            ("dining", "餐饮", 7, 600.0, 0.0),
            ("other", "其他", 3, 400.0, 0.0),
        ],
    )
    _write_run(
        root,
        "run_202602",
        year=2026,
        month=2,
        categories=[
            ("dining", "餐饮", 10, 2700.0, 0.0),
            ("other", "其他", 2, 300.0, 0.0),
        ],
    )
    _write_run(
        root,
        "run_202603",
        year=2026,
        month=3,
        categories=[
            ("dining", "餐饮", 5, 900.0, 0.0),
            ("other", "其他", 2, 300.0, 0.0),
        ],
    )
    _write_run(
        root,
        "run_202604",
        year=2026,
        month=4,
        categories=[
            ("other", "其他", 0, 0.0, 0.0),
        ],
    )
    _write_run(
        root,
        "run_unassigned",
        year=2026,
        month=5,
        categories=[
            ("misc", "杂项", 1, 50.0, 0.0),
        ],
    )

    add_bill_from_run(root, profile_id, "run_202501")
    add_bill_from_run(root, profile_id, "run_202601")
    add_bill_from_run(root, profile_id, "run_202602")
    add_bill_from_run(root, profile_id, "run_202603")
    add_bill_from_run(root, profile_id, "run_202604")
    add_bill_from_run(root, profile_id, "run_unassigned", period_year=None, period_month=None)

    # 触发一致性异常：缺少 category.summary.csv
    (root / "runs" / "run_202603" / "output" / "category.summary.csv").unlink()
    return profile_id


class ProfileReviewAnalyticsTests(unittest.TestCase):
    def test_build_profile_review_metrics_and_anomalies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_id = _prepare_profile(root)

            result = build_profile_review(root, profile_id, months=12)

            self.assertEqual(result["scope"]["profile_id"], profile_id)
            self.assertEqual(result["scope"]["data_source"], "profile_bills")

            monthly_points = result["monthly_points"]
            self.assertGreaterEqual(len(monthly_points), 5)
            jan_2026 = next(
                item for item in monthly_points if item["year"] == 2026 and item["month"] == 1
            )
            self.assertAlmostEqual(float(jan_2026["yoy_expense_rate"]), 0.25, places=4)
            feb_2026 = next(
                item for item in monthly_points if item["year"] == 2026 and item["month"] == 2
            )
            self.assertIsNone(feb_2026["yoy_expense_rate"])

            anomaly_codes = {str(item["code"]) for item in result["anomalies"]}
            self.assertIn("unassigned_period", anomaly_codes)
            self.assertIn("empty_period", anomaly_codes)
            self.assertIn("mom_expense_spike", anomaly_codes)
            self.assertIn("mom_expense_drop", anomaly_codes)
            self.assertIn("category_concentration_spike", anomaly_codes)
            self.assertIn("integrity_issue", anomaly_codes)
            self.assertGreater(len(result["integrity_issues"]), 0)

    def test_build_profile_review_year_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_id = _prepare_profile(root)

            result = build_profile_review(root, profile_id, year=2026, months=6)
            self.assertEqual(result["scope"]["year"], 2026)
            for item in result["monthly_points"]:
                self.assertEqual(int(item["year"]), 2026)

    def test_profile_review_api(self) -> None:
        if TestClient is None:
            self.skipTest("fastapi TestClient 不可用（缺少 httpx）")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_id = _prepare_profile(root)
            app = create_app(root)
            with TestClient(app) as client:
                ok_resp = client.get(f"/api/profiles/{profile_id}/review", params={"months": 6})
                self.assertEqual(ok_resp.status_code, 200)
                payload = ok_resp.json()
                self.assertIn("scope", payload)
                self.assertIn("overview", payload)
                self.assertIn("monthly_points", payload)
                self.assertIn("anomalies", payload)

                not_found_resp = client.get("/api/profiles/not_exists/review")
                self.assertEqual(not_found_resp.status_code, 404)

                invalid_resp = client.get(f"/api/profiles/{profile_id}/review", params={"months": 4})
                self.assertEqual(invalid_resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
