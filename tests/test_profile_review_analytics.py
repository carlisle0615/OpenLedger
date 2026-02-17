import json
import tempfile
import unittest
from pathlib import Path

from openledger.application.services.review_engine import build_profile_review
from openledger.infrastructure.persistence.sqlalchemy.profile_store import add_bill_from_run, create_profile
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


def _write_run_with_flow_breakdown(
    root: Path,
    run_id: str,
    *,
    year: int,
    month: int,
    sum_expense: float,
    sum_income: float,
    sum_refund: float,
    sum_transfer: float,
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
    (run_dir / "state.json").write_text(
        json.dumps(state, ensure_ascii=False),
        encoding="utf-8",
    )

    rows: list[tuple[str, float]] = []
    if sum_expense != 0:
        rows.append(("expense", float(sum_expense)))
    if sum_income != 0:
        rows.append(("income", float(sum_income)))
    if sum_refund != 0:
        rows.append(("refund", float(sum_refund)))
    if sum_transfer != 0:
        rows.append(("transfer", float(sum_transfer)))
    if not rows:
        rows.append(("other", 0.0))

    count = len(rows)
    sum_amount = float(sum_expense + sum_income + sum_refund + sum_transfer)
    summary_lines = [
        "category_id,category_name,count,sum_amount,sum_expense,sum_income,sum_refund,sum_transfer",
        (
            f"other,其他,{count},"
            f"{sum_amount:.2f},{float(sum_expense):.2f},{float(sum_income):.2f},"
            f"{float(sum_refund):.2f},{float(sum_transfer):.2f}"
        ),
    ]
    (out_dir / "category.summary.csv").write_text(
        "\n".join(summary_lines) + "\n",
        encoding="utf-8",
    )

    trade_date = f"{year:04d}-{month:02d}-01"
    categorized_lines = ["txn_id,trade_date,amount,category_id,category_name,ignored,flow"]
    for idx, (flow, amount) in enumerate(rows, start=1):
        categorized_lines.append(
            f"{run_id}_{idx},{trade_date},{amount:.2f},other,其他,false,{flow}"
        )
    (out_dir / "unified.transactions.categorized.csv").write_text(
        "\n".join(categorized_lines) + "\n",
        encoding="utf-8",
    )


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
            self.assertTrue(
                any(
                    str(item.get("category_id")) == "dining"
                    for item in jan_2026["category_expense_breakdown"]
                )
            )
            self.assertIn("expense_top_transactions", jan_2026)
            self.assertGreaterEqual(
                len(jan_2026["expense_top_transactions"].get("__all__", [])),
                1,
            )
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

    def test_review_overview_is_closed_with_refund_and_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = create_profile(root, "Bob")
            profile_id = str(profile["id"])

            _write_run_with_flow_breakdown(
                root,
                "run_closed_loop",
                year=2026,
                month=1,
                sum_expense=-100.0,
                sum_income=200.0,
                sum_refund=10.0,
                sum_transfer=20.0,
            )
            add_bill_from_run(root, profile_id, "run_closed_loop")

            result = build_profile_review(root, profile_id, year=2026, months=12)
            overview = result["overview"]

            self.assertAlmostEqual(float(overview["total_income"]), 230.0, places=4)
            self.assertAlmostEqual(float(overview["total_expense"]), 100.0, places=4)
            self.assertAlmostEqual(float(overview["net"]), 130.0, places=4)
            self.assertAlmostEqual(
                float(overview["net"]),
                float(overview["total_income"]) - float(overview["total_expense"]),
                places=4,
            )

            points = result["monthly_points"]
            self.assertEqual(len(points), 1)
            self.assertAlmostEqual(float(points[0]["income"]), 230.0, places=4)
            self.assertAlmostEqual(float(points[0]["expense"]), 100.0, places=4)
            self.assertAlmostEqual(float(points[0]["net"]), 130.0, places=4)
            self.assertAlmostEqual(float(points[0]["salary_income"]), 0.0, places=4)
            self.assertAlmostEqual(float(points[0]["subsidy_income"]), 0.0, places=4)
            self.assertAlmostEqual(float(points[0]["transfer_income"]), 20.0, places=4)
            self.assertAlmostEqual(float(points[0]["other_income"]), 210.0, places=4)
            self.assertIn("income_top_transactions", points[0])
            self.assertIn("expense_top_transactions", points[0])
            self.assertGreaterEqual(
                len(points[0]["income_top_transactions"]["transfer"]),
                1,
            )
            self.assertGreaterEqual(
                len(points[0]["expense_top_transactions"].get("__all__", [])),
                1,
            )
            self.assertEqual(len(points[0]["category_expense_breakdown"]), 1)
            self.assertEqual(points[0]["category_expense_breakdown"][0]["category_id"], "other")
            self.assertAlmostEqual(
                float(points[0]["category_expense_breakdown"][0]["expense"]),
                100.0,
                places=4,
            )

    def test_review_income_breakdown_salary_and_subsidy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = create_profile(root, "Carol")
            profile_id = str(profile["id"])

            _write_run(
                root,
                "run_income_breakdown",
                year=2026,
                month=6,
                categories=[
                    ("salary_wages", "工资薪金", 1, 0.0, 10000.0),
                    ("year_end_bonus", "年终奖", 1, 0.0, 1200.0),
                    ("government_subsidy", "政府补贴", 1, 0.0, 800.0),
                    ("stock_income", "股票收益", 1, 0.0, 200.0),
                ],
            )
            add_bill_from_run(root, profile_id, "run_income_breakdown")

            result = build_profile_review(root, profile_id, year=2026, months=12)
            overview = result["overview"]
            points = result["monthly_points"]
            self.assertEqual(len(points), 1)

            self.assertAlmostEqual(float(overview["total_income"]), 12200.0, places=4)
            self.assertAlmostEqual(float(overview["salary_income"]), 11200.0, places=4)
            self.assertAlmostEqual(float(overview["subsidy_income"]), 800.0, places=4)
            self.assertAlmostEqual(float(overview["transfer_income"]), 0.0, places=4)
            self.assertAlmostEqual(float(overview["other_income"]), 200.0, places=4)
            self.assertAlmostEqual(
                float(overview["salary_income"])
                + float(overview["subsidy_income"])
                + float(overview["transfer_income"])
                + float(overview["other_income"]),
                float(overview["total_income"]),
                places=4,
            )
            self.assertAlmostEqual(float(points[0]["salary_income"]), 11200.0, places=4)
            self.assertAlmostEqual(float(points[0]["subsidy_income"]), 800.0, places=4)
            self.assertAlmostEqual(float(points[0]["transfer_income"]), 0.0, places=4)
            self.assertAlmostEqual(float(points[0]["other_income"]), 200.0, places=4)
            self.assertIn("income_top_transactions", points[0])
            self.assertIn("expense_top_transactions", points[0])
            self.assertEqual(len(points[0]["income_top_transactions"]["transfer"]), 0)
            self.assertEqual(len(points[0]["expense_top_transactions"].get("__all__", [])), 0)

    def test_profile_review_api(self) -> None:
        if TestClient is None:
            self.skipTest("fastapi TestClient 不可用（缺少 httpx）")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_id = _prepare_profile(root)
            app = create_app(root)
            with TestClient(app) as client:
                ok_resp = client.get(f"/api/v2/profiles/{profile_id}/review", params={"months": 6})
                self.assertEqual(ok_resp.status_code, 200)
                envelope = ok_resp.json()
                self.assertIn("data", envelope)
                self.assertIn("meta", envelope)
                payload = envelope["data"]
                self.assertIn("scope", payload)
                self.assertIn("overview", payload)
                self.assertIn("monthly_points", payload)
                self.assertIn("anomalies", payload)
                self.assertIn("transfer_income", payload["overview"])
                self.assertIn("transfer_income", payload["monthly_points"][0])
                self.assertIn("income_top_transactions", payload["monthly_points"][0])
                self.assertIn("expense_top_transactions", payload["monthly_points"][0])
                self.assertIn("category_expense_breakdown", payload["monthly_points"][0])

                not_found_resp = client.get("/api/v2/profiles/not_exists/review")
                self.assertEqual(not_found_resp.status_code, 404)
                not_found_payload = not_found_resp.json()
                self.assertIn("error", not_found_payload)
                self.assertIn("request_id", not_found_payload)

                invalid_resp = client.get(f"/api/v2/profiles/{profile_id}/review", params={"months": 4})
                self.assertEqual(invalid_resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
