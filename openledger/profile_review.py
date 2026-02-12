from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .profiles import check_profile_integrity, load_profile


class _RawModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _RawBillTotals(_RawModel):
    sum_amount: float = 0.0
    sum_expense: float = 0.0
    sum_income: float = 0.0
    count: float = 0.0
    net: float | None = None


class _RawCategorySummary(_RawModel):
    category_id: str = ""
    category_name: str = ""
    count: float = 0.0
    sum_expense: float = 0.0
    sum_income: float = 0.0


class _RawBill(_RawModel):
    run_id: str
    period_key: str = ""
    year: int | None = None
    month: int | None = None
    totals: _RawBillTotals = Field(default_factory=_RawBillTotals)
    category_summary: list[_RawCategorySummary] = Field(default_factory=list)


class _RawProfile(_RawModel):
    id: str
    name: str
    bills: list[_RawBill] = Field(default_factory=list)


class _RawIntegrityIssue(_RawModel):
    run_id: str = ""
    period_key: str = ""
    issue: str
    path: str | None = None


class _RawIntegrityResult(_RawModel):
    profile_id: str
    issues: list[_RawIntegrityIssue] = Field(default_factory=list)


@dataclass(frozen=True)
class _BillMetrics:
    run_id: str
    period_key: str
    year: int | None
    month: int | None
    expense: float
    income: float
    net: float
    tx_count: int
    category_expense: dict[str, float]
    category_income: dict[str, float]
    category_count: dict[str, int]
    category_names: dict[str, str]


@dataclass
class _MonthlyAggregate:
    year: int
    month: int
    period_key: str
    run_id: str
    expense: float = 0.0
    income: float = 0.0
    net: float = 0.0
    tx_count: int = 0
    category_expense: dict[str, float] = field(default_factory=dict)


def _round2(value: float) -> float:
    return round(float(value), 2)


def _round4(value: float) -> float:
    return round(float(value), 4)


def _normalized_period_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _severity_rank(level: str) -> int:
    if level == "high":
        return 0
    if level == "medium":
        return 1
    return 2


def _issue_label(issue: str) -> str:
    if issue == "missing_period_key":
        return "账期缺失"
    if issue == "missing_run_dir":
        return "run 目录缺失"
    if issue == "missing_summary_csv":
        return "缺少 category.summary.csv"
    if issue == "empty_summary_csv":
        return "category.summary.csv 为空"
    if issue == "missing_categorized_csv":
        return "缺少 unified.transactions.categorized.csv"
    if issue == "empty_categorized_csv":
        return "unified.transactions.categorized.csv 为空"
    return issue


def _normalize_bill(raw_bill: _RawBill) -> _BillMetrics:
    totals = raw_bill.totals
    expense = abs(float(totals.sum_expense))
    income = abs(float(totals.sum_income))
    net_raw = totals.net if totals.net is not None else totals.sum_amount
    net = float(net_raw)
    tx_count = int(round(float(totals.count)))

    category_expense: dict[str, float] = {}
    category_income: dict[str, float] = {}
    category_count: dict[str, int] = {}
    category_names: dict[str, str] = {}

    for item in raw_bill.category_summary:
        category_id = str(item.category_id or "").strip() or "other"
        category_name = str(item.category_name or "").strip() or "其他"
        exp = abs(float(item.sum_expense))
        inc = abs(float(item.sum_income))
        cnt = int(round(float(item.count)))

        category_names[category_id] = category_name
        category_expense[category_id] = category_expense.get(category_id, 0.0) + exp
        category_income[category_id] = category_income.get(category_id, 0.0) + inc
        category_count[category_id] = category_count.get(category_id, 0) + cnt

    if not category_expense and expense > 0:
        category_names["other"] = "其他"
        category_expense["other"] = expense
        category_count["other"] = tx_count
    if not category_income and income > 0:
        category_names["other"] = "其他"
        category_income["other"] = income
        category_count["other"] = category_count.get("other", 0) + tx_count

    return _BillMetrics(
        run_id=str(raw_bill.run_id or "").strip(),
        period_key=str(raw_bill.period_key or "").strip(),
        year=raw_bill.year,
        month=raw_bill.month,
        expense=expense,
        income=income,
        net=net,
        tx_count=tx_count,
        category_expense=category_expense,
        category_income=category_income,
        category_count=category_count,
        category_names=category_names,
    )


def _aggregate_monthly(bills: list[_BillMetrics]) -> list[_MonthlyAggregate]:
    monthly: dict[tuple[int, int], _MonthlyAggregate] = {}
    for bill in bills:
        if bill.year is None or bill.month is None:
            continue
        month_key = (bill.year, bill.month)
        period_key = bill.period_key or _normalized_period_key(bill.year, bill.month)
        if month_key not in monthly:
            monthly[month_key] = _MonthlyAggregate(
                year=bill.year,
                month=bill.month,
                period_key=period_key,
                run_id=bill.run_id,
            )
        slot = monthly[month_key]
        slot.expense += bill.expense
        slot.income += bill.income
        slot.net += bill.net
        slot.tx_count += bill.tx_count
        for category_id, value in bill.category_expense.items():
            slot.category_expense[category_id] = (
                slot.category_expense.get(category_id, 0.0) + value
            )
    return [monthly[key] for key in sorted(monthly.keys())]


def _build_category_slices(
    bills: list[_BillMetrics],
    *,
    top_n: int = 8,
) -> list[dict[str, float | int | str]]:
    category_expense: dict[str, float] = {}
    category_income: dict[str, float] = {}
    category_count: dict[str, int] = {}
    category_names: dict[str, str] = {}

    for bill in bills:
        for category_id, value in bill.category_expense.items():
            category_expense[category_id] = (
                category_expense.get(category_id, 0.0) + value
            )
            category_names[category_id] = bill.category_names.get(
                category_id, category_id
            )
        for category_id, value in bill.category_income.items():
            category_income[category_id] = category_income.get(category_id, 0.0) + value
            category_names[category_id] = bill.category_names.get(
                category_id, category_id
            )
        for category_id, value in bill.category_count.items():
            category_count[category_id] = category_count.get(category_id, 0) + value
            category_names[category_id] = bill.category_names.get(
                category_id, category_id
            )

    rows: list[dict[str, float | int | str]] = []
    for category_id, expense in category_expense.items():
        rows.append(
            {
                "category_id": category_id,
                "category_name": category_names.get(category_id, category_id),
                "expense": _round2(expense),
                "income": _round2(category_income.get(category_id, 0.0)),
                "tx_count": int(category_count.get(category_id, 0)),
            }
        )
    rows.sort(key=lambda item: float(item["expense"]), reverse=True)

    if len(rows) > top_n:
        top_rows = rows[:top_n]
        tail_rows = rows[top_n:]
        others_expense = sum(float(item["expense"]) for item in tail_rows)
        others_income = sum(float(item["income"]) for item in tail_rows)
        others_count = sum(int(item["tx_count"]) for item in tail_rows)
        top_rows.append(
            {
                "category_id": "other",
                "category_name": "其他",
                "expense": _round2(others_expense),
                "income": _round2(others_income),
                "tx_count": others_count,
            }
        )
        rows = top_rows

    total_expense = sum(float(item["expense"]) for item in rows)
    if total_expense <= 0:
        total_expense = 0.0

    output: list[dict[str, float | int | str]] = []
    for item in rows:
        share = float(item["expense"]) / total_expense if total_expense > 0 else 0.0
        output.append(
            {
                "category_id": str(item["category_id"]),
                "category_name": str(item["category_name"]),
                "expense": _round2(float(item["expense"])),
                "income": _round2(float(item["income"])),
                "tx_count": int(item["tx_count"]),
                "share_expense": _round4(share),
            }
        )
    return output


def build_profile_review(
    root: Path,
    profile_id: str,
    *,
    year: int | None = None,
    months: int = 12,
) -> dict[str, object]:
    raw_profile = _RawProfile.model_validate(load_profile(root, profile_id))
    raw_integrity = _RawIntegrityResult.model_validate(
        check_profile_integrity(root, profile_id)
    )

    bills = [_normalize_bill(item) for item in raw_profile.bills]
    complete_bills = [
        bill for bill in bills if bill.year is not None and bill.month is not None
    ]
    scoped_bills = [bill for bill in bills if year is None or bill.year == year]
    scoped_complete_bills = [
        bill for bill in complete_bills if year is None or bill.year == year
    ]
    unassigned_bills = [
        bill for bill in bills if bill.year is None or bill.month is None
    ]

    all_monthly = _aggregate_monthly(complete_bills)
    scoped_monthly = _aggregate_monthly(scoped_complete_bills)
    all_monthly_map = {(item.year, item.month): item for item in all_monthly}

    monthly_points_full: list[dict[str, object]] = []
    for idx, item in enumerate(scoped_monthly):
        prev_item = scoped_monthly[idx - 1] if idx > 0 else None
        mom_rate: float | None = None
        if prev_item and prev_item.expense > 0:
            mom_rate = _round4((item.expense - prev_item.expense) / prev_item.expense)

        yoy_item = all_monthly_map.get((item.year - 1, item.month))
        yoy_rate: float | None = None
        if yoy_item and yoy_item.expense > 0:
            yoy_rate = _round4((item.expense - yoy_item.expense) / yoy_item.expense)

        monthly_points_full.append(
            {
                "period_key": item.period_key
                or _normalized_period_key(item.year, item.month),
                "year": item.year,
                "month": item.month,
                "expense": _round2(item.expense),
                "income": _round2(item.income),
                "net": _round2(item.net),
                "tx_count": int(item.tx_count),
                "mom_expense_rate": mom_rate,
                "yoy_expense_rate": yoy_rate,
                "_run_id": item.run_id,
                "_top_share": _round4(
                    max(item.category_expense.values()) / item.expense
                    if item.expense > 0 and item.category_expense
                    else 0.0
                ),
            }
        )

    months_window = max(6, min(120, int(months)))
    if len(monthly_points_full) > months_window:
        monthly_points_display = monthly_points_full[-months_window:]
    else:
        monthly_points_display = monthly_points_full

    yearly: dict[int, dict[str, float | int]] = {}
    for item in all_monthly:
        year_slot = yearly.get(item.year)
        if year_slot is None:
            year_slot = {"expense": 0.0, "income": 0.0, "net": 0.0, "tx_count": 0}
            yearly[item.year] = year_slot
        year_slot["expense"] = float(year_slot["expense"]) + item.expense
        year_slot["income"] = float(year_slot["income"]) + item.income
        year_slot["net"] = float(year_slot["net"]) + item.net
        year_slot["tx_count"] = int(year_slot["tx_count"]) + item.tx_count

    yearly_points: list[dict[str, object]] = []
    for year_key in sorted(yearly.keys()):
        slot = yearly[year_key]
        yearly_points.append(
            {
                "year": int(year_key),
                "expense": _round2(float(slot["expense"])),
                "income": _round2(float(slot["income"])),
                "net": _round2(float(slot["net"])),
                "tx_count": int(slot["tx_count"]),
            }
        )

    category_slices = _build_category_slices(scoped_bills)

    anomalies: list[dict[str, object]] = []

    for bill in unassigned_bills:
        anomalies.append(
            {
                "code": "unassigned_period",
                "severity": "medium",
                "title": "账期未指定年月",
                "period_key": bill.period_key,
                "run_id": bill.run_id,
                "message": "该账期未绑定具体年/月，无法进入月度分析。",
                "value": None,
                "baseline": None,
                "delta_rate": None,
            }
        )

    for point in monthly_points_display:
        if int(point["tx_count"]) <= 0:
            anomalies.append(
                {
                    "code": "empty_period",
                    "severity": "medium",
                    "title": "账期交易数为 0",
                    "period_key": str(point["period_key"]),
                    "run_id": str(point["_run_id"]),
                    "message": "该账期交易条数为 0，请核对归档与产物。",
                    "value": float(point["tx_count"]),
                    "baseline": None,
                    "delta_rate": None,
                }
            )

    for idx, point in enumerate(monthly_points_display):
        if idx == 0:
            continue
        prev = monthly_points_display[idx - 1]
        prev_expense = float(prev["expense"])
        curr_expense = float(point["expense"])
        if prev_expense <= 0:
            continue
        delta = curr_expense - prev_expense
        rate = delta / prev_expense
        if rate >= 0.5 and delta >= 1000:
            anomalies.append(
                {
                    "code": "mom_expense_spike",
                    "severity": "high",
                    "title": "支出环比异常上涨",
                    "period_key": str(point["period_key"]),
                    "run_id": str(point["_run_id"]),
                    "message": "当月支出较上月增幅较大，请确认是否存在异常消费或归档错误。",
                    "value": _round2(curr_expense),
                    "baseline": _round2(prev_expense),
                    "delta_rate": _round4(rate),
                }
            )
        if rate <= -0.5 and abs(delta) >= 1000:
            anomalies.append(
                {
                    "code": "mom_expense_drop",
                    "severity": "high",
                    "title": "支出环比异常下降",
                    "period_key": str(point["period_key"]),
                    "run_id": str(point["_run_id"]),
                    "message": "当月支出较上月降幅较大，请确认是否漏记或账期划分变化。",
                    "value": _round2(curr_expense),
                    "baseline": _round2(prev_expense),
                    "delta_rate": _round4(rate),
                }
            )

    for idx, point in enumerate(monthly_points_display):
        if idx == 0:
            continue
        prev = monthly_points_display[idx - 1]
        curr_share = float(point["_top_share"])
        prev_share = float(prev["_top_share"])
        delta_share = curr_share - prev_share
        if curr_share >= 0.6 and delta_share >= 0.25:
            anomalies.append(
                {
                    "code": "category_concentration_spike",
                    "severity": "medium",
                    "title": "分类集中度异常上升",
                    "period_key": str(point["period_key"]),
                    "run_id": str(point["_run_id"]),
                    "message": "Top1 分类支出占比显著上升，请核对分类规则与消费结构。",
                    "value": _round4(curr_share),
                    "baseline": _round4(prev_share),
                    "delta_rate": _round4(delta_share),
                }
            )

    for issue in raw_integrity.issues:
        anomalies.append(
            {
                "code": "integrity_issue",
                "severity": "high",
                "title": "归档一致性异常",
                "period_key": issue.period_key,
                "run_id": issue.run_id,
                "message": _issue_label(issue.issue),
                "value": None,
                "baseline": None,
                "delta_rate": None,
            }
        )

    anomalies.sort(
        key=lambda item: (
            _severity_rank(str(item["severity"])),
            str(item["period_key"]),
            str(item["code"]),
        )
    )

    integrity_issues = [
        {
            "run_id": issue.run_id,
            "period_key": issue.period_key,
            "issue": issue.issue,
            "path": issue.path,
        }
        for issue in raw_integrity.issues
    ]

    overview = {
        "total_expense": _round2(sum(item.expense for item in scoped_bills)),
        "total_income": _round2(sum(item.income for item in scoped_bills)),
        "net": _round2(sum(item.net for item in scoped_bills)),
        "period_count": len(scoped_monthly),
        "anomaly_count": len(anomalies),
    }

    monthly_points = [
        {
            "period_key": str(item["period_key"]),
            "year": int(item["year"]),
            "month": int(item["month"]),
            "expense": float(item["expense"]),
            "income": float(item["income"]),
            "net": float(item["net"]),
            "tx_count": int(item["tx_count"]),
            "mom_expense_rate": item["mom_expense_rate"],
            "yoy_expense_rate": item["yoy_expense_rate"],
        }
        for item in monthly_points_display
    ]

    return {
        "scope": {
            "profile_id": raw_profile.id,
            "profile_name": raw_profile.name,
            "data_source": "profile_bills",
            "year": year,
            "months": months_window,
            "total_bills": len(bills),
            "scoped_bills": len(scoped_bills),
            "complete_period_bills": len(scoped_complete_bills),
            "unassigned_bills": len(unassigned_bills),
        },
        "overview": overview,
        "monthly_points": monthly_points,
        "yearly_points": yearly_points,
        "category_slices": category_slices,
        "anomalies": anomalies,
        "integrity_issues": integrity_issues,
    }
