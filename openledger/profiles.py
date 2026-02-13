from __future__ import annotations

import calendar
import csv
import json
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .state import load_json, safe_rel_path, utc_now_iso

_MISSING = object()


def _db_path(root: Path) -> Path:
    configured = str(os.environ.get("OPENLEDGER_PROFILES_DB_PATH", "") or "").strip()
    if not configured:
        return root / "profiles.db"
    path = Path(configured)
    if not path.is_absolute():
        path = root / path
    return path


def _connect(root: Path) -> sqlite3.Connection:
    db_path = _db_path(root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            period_key TEXT,
            year INTEGER,
            month INTEGER,
            period_mode TEXT,
            period_day INTEGER,
            period_start TEXT,
            period_end TEXT,
            period_label TEXT,
            cross_month INTEGER,
            created_at TEXT,
            updated_at TEXT,
            outputs_json TEXT,
            UNIQUE(profile_id, run_id),
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS run_bindings (
            run_id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bills_profile_period ON bills(profile_id, period_key)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_run_bindings_profile ON run_bindings(profile_id)"
    )


def _slugify(value: str) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s.strip("_")


def _new_profile_id(name: str) -> str:
    base = _slugify(name)
    suffix = secrets.token_hex(3)
    if base:
        return f"{base}_{suffix}"
    return f"profile_{suffix}"


def _to_int(value: Any) -> int | None:
    try:
        v = int(value)
    except Exception:
        return None
    return v


def _to_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        s = str(value).strip()
        if s == "":
            return 0.0
        return float(s)
    except Exception:
        return 0.0


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


def _json_loads(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _extract_period(state: dict[str, Any]) -> tuple[int | None, int | None, str, int, str]:
    opts = state.get("options", {}) if isinstance(state.get("options"), dict) else {}
    year = _to_int(opts.get("period_year"))
    month = _to_int(opts.get("period_month"))
    mode = str(opts.get("period_mode") or "billing").strip() or "billing"
    day = _to_int(opts.get("period_day")) or 20

    if not year or not month:
        created_at = str(state.get("created_at") or "")
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            year = year or dt.year
            month = month or dt.month
        except Exception:
            pass

    period_key = f"{year:04d}-{month:02d}" if year and month else ""
    return year, month, period_key, day, mode


def _calc_period_range(
    year: int | None,
    month: int | None,
    mode: str,
    day: int,
) -> tuple[date | None, date | None, str]:
    if not year or not month:
        return None, None, ""
    if mode == "calendar":
        last_day = calendar.monthrange(year, month)[1]
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)
        label = f"{year:04d}-{month:02d} 自然月"
        return start_date, end_date, label
    start_year, start_month = (year - 1, 12) if month == 1 else (year, month - 1)
    prev_last_day = calendar.monthrange(start_year, start_month)[1]
    end_last_day = calendar.monthrange(year, month)[1]
    prev_end_day = min(day, prev_last_day)
    end_day = min(day, end_last_day)
    prev_end_date = date(start_year, start_month, prev_end_day)
    start_date = prev_end_date + timedelta(days=1)
    end_date = date(year, month, end_day)
    label = f"{year:04d}-{month:02d} 账期({day}日)"
    return start_date, end_date, label


def _read_category_summary(path: Path) -> tuple[dict[str, float], list[dict[str, Any]]]:
    if not path.exists():
        return {}, []
    totals = {
        "sum_amount": 0.0,
        "sum_expense": 0.0,
        "sum_income": 0.0,
        "sum_refund": 0.0,
        "sum_transfer": 0.0,
        "count": 0.0,
    }
    categories: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat = {
                "category_id": str(row.get("category_id", "")).strip(),
                "category_name": str(row.get("category_name", "")).strip(),
                "count": _to_float(row.get("count")),
                "sum_amount": _to_float(row.get("sum_amount")),
                "sum_expense": _to_float(row.get("sum_expense")),
                "sum_income": _to_float(row.get("sum_income")),
                "sum_refund": _to_float(row.get("sum_refund")),
                "sum_transfer": _to_float(row.get("sum_transfer")),
            }
            categories.append(cat)
            for key in totals:
                totals[key] += float(cat.get(key, 0.0))
    totals["net"] = totals.get("sum_amount", 0.0)
    return totals, categories


def _read_category_summary_from_categorized(path: Path) -> tuple[dict[str, float], list[dict[str, Any]]]:
    if not path.exists():
        return {}, []

    totals = {
        "sum_amount": 0.0,
        "sum_expense": 0.0,
        "sum_income": 0.0,
        "sum_refund": 0.0,
        "sum_transfer": 0.0,
        "count": 0.0,
    }
    grouped: dict[str, dict[str, Any]] = {}

    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if _to_bool(row.get("ignored")) or _to_bool(row.get("final_ignored")):
                continue
            amount = _to_float(row.get("amount"))
            category_id = str(row.get("category_id") or row.get("final_category_id") or "").strip() or "other"
            category_name = str(row.get("category_name") or row.get("category") or "").strip() or category_id
            flow = str(row.get("flow") or "").strip().lower()

            cat = grouped.get(category_id)
            if cat is None:
                cat = {
                    "category_id": category_id,
                    "category_name": category_name,
                    "count": 0.0,
                    "sum_amount": 0.0,
                    "sum_expense": 0.0,
                    "sum_income": 0.0,
                    "sum_refund": 0.0,
                    "sum_transfer": 0.0,
                }
                grouped[category_id] = cat
            elif not str(cat.get("category_name") or "").strip() and category_name:
                cat["category_name"] = category_name

            cat["count"] += 1.0
            cat["sum_amount"] += amount
            totals["count"] += 1.0
            totals["sum_amount"] += amount

            if amount < 0:
                cat["sum_expense"] += amount
                totals["sum_expense"] += amount
            elif amount > 0:
                if flow == "refund":
                    cat["sum_refund"] += amount
                    totals["sum_refund"] += amount
                elif flow == "transfer":
                    cat["sum_transfer"] += amount
                    totals["sum_transfer"] += amount
                else:
                    cat["sum_income"] += amount
                    totals["sum_income"] += amount

    totals["net"] = totals.get("sum_amount", 0.0)
    categories = sorted(
        grouped.values(),
        key=lambda item: (abs(float(item.get("sum_amount", 0.0))), str(item.get("category_id") or "")),
        reverse=True,
    )
    return totals, categories


def _resolve_bill_outputs(
    root: Path,
    run_id: str,
    outputs: dict[str, Any],
) -> tuple[dict[str, str], Path, Path]:
    run_dir = root / "runs" / run_id
    summary_rel = str(outputs.get("summary_csv") or "").strip()
    categorized_rel = str(outputs.get("categorized_csv") or "").strip()

    summary_path = (root / summary_rel) if summary_rel else run_dir / "output" / "category.summary.csv"
    categorized_path = (
        (root / categorized_rel)
        if categorized_rel
        else run_dir / "output" / "unified.transactions.categorized.csv"
    )

    resolved_outputs = {
        "summary_csv": safe_rel_path(root, summary_path) if summary_path.exists() else summary_rel,
        "categorized_csv": safe_rel_path(root, categorized_path) if categorized_path.exists() else categorized_rel,
    }
    return resolved_outputs, summary_path, categorized_path


def _recompute_bill_metrics(summary_path: Path, categorized_path: Path) -> tuple[dict[str, float], list[dict[str, Any]]]:
    if _csv_has_header(categorized_path):
        return _read_category_summary_from_categorized(categorized_path)
    if _csv_has_header(summary_path):
        return _read_category_summary(summary_path)
    return {}, []


def _csv_has_header(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            row = next(reader, [])
        return any(str(cell).strip() for cell in row)
    except Exception:
        return False


def _validate_final_outputs(summary_path: Path, categorized_path: Path) -> None:
    missing: list[str] = []
    empty: list[str] = []

    if not summary_path.exists():
        missing.append("category.summary.csv")
    elif not _csv_has_header(summary_path):
        empty.append("category.summary.csv")

    if not categorized_path.exists():
        missing.append("unified.transactions.categorized.csv")
    elif not _csv_has_header(categorized_path):
        empty.append("unified.transactions.categorized.csv")

    if missing or empty:
        details: list[str] = []
        if missing:
            details.append(f"missing={','.join(missing)}")
        if empty:
            details.append(f"empty={','.join(empty)}")
        raise ValueError("finalize outputs incomplete: " + "; ".join(details))


def _rows(conn: sqlite3.Connection, sql: str, args: Iterable[Any] = ()) -> list[sqlite3.Row]:
    cur = conn.execute(sql, tuple(args))
    return list(cur.fetchall())


def list_profiles(root: Path) -> list[dict[str, Any]]:
    with _connect(root) as conn:
        _init_db(conn)
        rows = _rows(
            conn,
            """
            SELECT p.id, p.name, p.created_at, p.updated_at, COUNT(b.id) AS bill_count
            FROM profiles p
            LEFT JOIN bills b ON p.id = b.profile_id
            GROUP BY p.id
            ORDER BY p.created_at
            """,
        )
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "bill_count": r["bill_count"],
        }
        for r in rows
    ]


def create_profile(root: Path, name: str) -> dict[str, Any]:
    profile_id = _new_profile_id(name)
    now = utc_now_iso()
    with _connect(root) as conn:
        _init_db(conn)
        conn.execute(
            "INSERT INTO profiles(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (profile_id, str(name or "").strip()[:80], now, now),
        )
    return load_profile(root, profile_id)


def load_profile(root: Path, profile_id: str) -> dict[str, Any]:
    with _connect(root) as conn:
        _init_db(conn)
        row = conn.execute(
            "SELECT id, name, created_at, updated_at FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        if not row:
            raise FileNotFoundError(profile_id)
        bills = _rows(
            conn,
            """
            SELECT * FROM bills
            WHERE profile_id = ?
            ORDER BY year, month, run_id
            """,
            (profile_id,),
        )

    out_bills: list[dict[str, Any]] = []
    for b in bills:
        outputs_payload = _json_loads(b["outputs_json"], {})
        try:
            outputs = dict(outputs_payload or {})
        except Exception:
            outputs = {}
        resolved_outputs, summary_path, categorized_path = _resolve_bill_outputs(
            root, str(b["run_id"] or "").strip(), outputs
        )
        totals, category_summary = _recompute_bill_metrics(summary_path, categorized_path)
        out_bills.append(
            {
                "run_id": b["run_id"],
                "period_key": b["period_key"],
                "year": b["year"],
                "month": b["month"],
                "period_mode": b["period_mode"],
                "period_day": b["period_day"],
                "period_start": b["period_start"],
                "period_end": b["period_end"],
                "period_label": b["period_label"],
                "cross_month": bool(b["cross_month"]),
                "created_at": b["created_at"],
                "updated_at": b["updated_at"],
                "outputs": resolved_outputs,
                "totals": totals,
                "category_summary": category_summary,
            }
        )

    return {
        "id": row["id"],
        "name": row["name"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "bills": out_bills,
    }


def update_profile(root: Path, profile_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    with _connect(root) as conn:
        _init_db(conn)
        row = conn.execute("SELECT id FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            raise FileNotFoundError(profile_id)
        if "name" in updates:
            conn.execute(
                "UPDATE profiles SET name = ?, updated_at = ? WHERE id = ?",
                (str(updates.get("name") or "").strip()[:80], utc_now_iso(), profile_id),
            )
    return load_profile(root, profile_id)


def _run_state_path(root: Path, run_id: str) -> Path:
    return root / "runs" / run_id / "state.json"


def _ensure_run_exists(root: Path, run_id: str) -> None:
    if not _run_state_path(root, run_id).exists():
        raise FileNotFoundError(f"run not found: {run_id}")


def _bill_owner_profile_id(conn: sqlite3.Connection, run_id: str) -> str:
    row = conn.execute(
        """
        SELECT profile_id
        FROM bills
        WHERE run_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (run_id,),
    ).fetchone()
    if not row:
        return ""
    return str(row["profile_id"] or "").strip()


def _legacy_state_profile_id(root: Path, run_id: str) -> str:
    state_path = _run_state_path(root, run_id)
    if not state_path.exists():
        return ""
    try:
        state = load_json(state_path)
    except Exception:
        return ""
    opts = state.get("options")
    if not isinstance(opts, dict):
        return ""
    return str(opts.get("profile_id") or "").strip()


def _upsert_run_binding_conn(conn: sqlite3.Connection, run_id: str, profile_id: str, now: str) -> None:
    conn.execute(
        """
        INSERT INTO run_bindings(run_id, profile_id, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            profile_id=excluded.profile_id,
            updated_at=excluded.updated_at
        """,
        (run_id, profile_id, now, now),
    )


def _binding_row(conn: sqlite3.Connection, run_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT run_id, profile_id, created_at, updated_at FROM run_bindings WHERE run_id = ?",
        (run_id,),
    ).fetchone()


def get_run_binding(root: Path, run_id: str) -> dict[str, Any] | None:
    run_id = str(run_id or "").strip()
    if not run_id:
        raise ValueError("missing run_id")
    _ensure_run_exists(root, run_id)

    with _connect(root) as conn:
        _init_db(conn)
        row = _binding_row(conn, run_id)
        if row:
            return {
                "run_id": run_id,
                "profile_id": str(row["profile_id"] or "").strip(),
                "created_at": str(row["created_at"] or ""),
                "updated_at": str(row["updated_at"] or ""),
            }

        inferred_profile_id = _bill_owner_profile_id(conn, run_id)
        if not inferred_profile_id:
            inferred_profile_id = _legacy_state_profile_id(root, run_id)
        if not inferred_profile_id:
            return None

        # lazy migration: if legacy state / bills has owner info, backfill to run_bindings.
        profile_row = conn.execute(
            "SELECT id FROM profiles WHERE id = ?",
            (inferred_profile_id,),
        ).fetchone()
        if not profile_row:
            return None
        now = utc_now_iso()
        _upsert_run_binding_conn(conn, run_id, inferred_profile_id, now)
        row = _binding_row(conn, run_id)
        if not row:
            return None
        return {
            "run_id": run_id,
            "profile_id": str(row["profile_id"] or "").strip(),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or ""),
        }


def get_run_binding_profile_id(root: Path, run_id: str) -> str:
    binding = get_run_binding(root, run_id)
    if not binding:
        return ""
    return str(binding.get("profile_id") or "").strip()


def set_run_binding(root: Path, run_id: str, profile_id: str) -> dict[str, Any]:
    run_id = str(run_id or "").strip()
    profile_id = str(profile_id or "").strip()
    if not run_id:
        raise ValueError("missing run_id")
    if not profile_id:
        raise ValueError("missing profile_id")
    _ensure_run_exists(root, run_id)

    with _connect(root) as conn:
        _init_db(conn)
        profile_row = conn.execute(
            "SELECT id FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        if not profile_row:
            raise FileNotFoundError(profile_id)

        bill_owner = _bill_owner_profile_id(conn, run_id)
        if bill_owner and bill_owner != profile_id:
            raise ValueError(f"run {run_id} 已归档到用户 {bill_owner}，不可绑定到 {profile_id}")

        now = utc_now_iso()
        _upsert_run_binding_conn(conn, run_id, profile_id, now)
        row = _binding_row(conn, run_id)
        if not row:
            raise RuntimeError("run binding save failed")
        return {
            "run_id": run_id,
            "profile_id": str(row["profile_id"] or "").strip(),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or ""),
        }


def clear_run_binding(root: Path, run_id: str) -> None:
    run_id = str(run_id or "").strip()
    if not run_id:
        raise ValueError("missing run_id")
    _ensure_run_exists(root, run_id)
    with _connect(root) as conn:
        _init_db(conn)
        conn.execute("DELETE FROM run_bindings WHERE run_id = ?", (run_id,))


def build_bill_from_run(root: Path, run_id: str) -> dict[str, Any]:
    run_dir = root / "runs" / run_id
    state_path = run_dir / "state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"run not found: {run_id}")
    state = load_json(state_path)
    year, month, period_key, period_day, period_mode = _extract_period(state)

    out_dir = run_dir / "output"
    summary_path = out_dir / "category.summary.csv"
    categorized_path = out_dir / "unified.transactions.categorized.csv"

    _validate_final_outputs(summary_path, categorized_path)

    outputs = {
        "summary_csv": safe_rel_path(root, summary_path) if summary_path.exists() else "",
        "categorized_csv": safe_rel_path(root, categorized_path) if categorized_path.exists() else "",
    }

    period_start, period_end, period_label = _calc_period_range(year, month, period_mode, period_day)
    cross_month = False
    if period_start and period_end:
        cross_month = (period_start.year, period_start.month) != (period_end.year, period_end.month)

    bill = {
        "run_id": run_id,
        "period_key": period_key,
        "year": year,
        "month": month,
        "period_mode": period_mode,
        "period_day": period_day,
        "period_start": period_start.isoformat() if period_start else "",
        "period_end": period_end.isoformat() if period_end else "",
        "period_label": period_label,
        "cross_month": cross_month,
        "created_at": str(state.get("created_at") or ""),
        "updated_at": utc_now_iso(),
        "outputs": outputs,
        "totals": {},
        "category_summary": [],
    }
    return bill


def _upsert_bill(conn: sqlite3.Connection, profile_id: str, bill: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO bills(
            profile_id, run_id, period_key, year, month, period_mode, period_day,
            period_start, period_end, period_label, cross_month,
            created_at, updated_at, outputs_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(profile_id, run_id) DO UPDATE SET
            period_key=excluded.period_key,
            year=excluded.year,
            month=excluded.month,
            period_mode=excluded.period_mode,
            period_day=excluded.period_day,
            period_start=excluded.period_start,
            period_end=excluded.period_end,
            period_label=excluded.period_label,
            cross_month=excluded.cross_month,
            updated_at=excluded.updated_at,
            outputs_json=excluded.outputs_json
        """,
        (
            profile_id,
            bill.get("run_id"),
            bill.get("period_key"),
            bill.get("year"),
            bill.get("month"),
            bill.get("period_mode"),
            bill.get("period_day"),
            bill.get("period_start"),
            bill.get("period_end"),
            bill.get("period_label"),
            1 if bill.get("cross_month") else 0,
            bill.get("created_at"),
            bill.get("updated_at"),
            _json_dumps(bill.get("outputs") or {}),
        ),
    )


def _normalize_period_override(period_year: Any, period_month: Any) -> tuple[int | None, int | None]:
    year = _to_int(period_year)
    month = _to_int(period_month)
    if year is None and month is None:
        return None, None
    if year is None or month is None:
        raise ValueError("period_year 和 period_month 需同时提供，或同时为空")
    if month < 1 or month > 12:
        raise ValueError("period_month 必须在 1~12")
    if year < 1900 or year > 2200:
        raise ValueError("period_year 超出支持范围")
    return year, month


def _apply_period_override(bill: dict[str, Any], year: int | None, month: int | None) -> None:
    if not year or not month:
        bill["year"] = None
        bill["month"] = None
        bill["period_key"] = ""
        bill["period_start"] = ""
        bill["period_end"] = ""
        bill["period_label"] = ""
        bill["cross_month"] = False
        return

    mode = str(bill.get("period_mode") or "billing").strip() or "billing"
    day = _to_int(bill.get("period_day")) or 20
    period_start, period_end, period_label = _calc_period_range(year, month, mode, day)
    bill["year"] = year
    bill["month"] = month
    bill["period_key"] = f"{year:04d}-{month:02d}"
    bill["period_start"] = period_start.isoformat() if period_start else ""
    bill["period_end"] = period_end.isoformat() if period_end else ""
    bill["period_label"] = period_label
    bill["cross_month"] = bool(
        period_start and period_end and (period_start.year, period_start.month) != (period_end.year, period_end.month)
    )


def _ensure_unique_period_binding(conn: sqlite3.Connection, profile_id: str, bill: dict[str, Any]) -> None:
    year = _to_int(bill.get("year"))
    month = _to_int(bill.get("month"))
    run_id = str(bill.get("run_id") or "").strip()
    if not year or not month or not run_id:
        return
    row = conn.execute(
        """
        SELECT run_id
        FROM bills
        WHERE profile_id = ? AND year = ? AND month = ? AND run_id != ?
        LIMIT 1
        """,
        (profile_id, year, month, run_id),
    ).fetchone()
    if row:
        raise ValueError(f"账期 {year:04d}-{month:02d} 已绑定 run {row['run_id']}，同月不能绑定多个 run")


def add_bill_from_run(
    root: Path,
    profile_id: str,
    run_id: str,
    *,
    period_year: Any = _MISSING,
    period_month: Any = _MISSING,
) -> dict[str, Any]:
    bill = build_bill_from_run(root, run_id)
    run_id = str(bill.get("run_id") or run_id).strip()
    now = utc_now_iso()
    if period_year is not _MISSING or period_month is not _MISSING:
        year, month = _normalize_period_override(period_year, period_month)
        _apply_period_override(bill, year, month)

    with _connect(root) as conn:
        _init_db(conn)
        row = conn.execute("SELECT id FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            raise FileNotFoundError(profile_id)
        binding_row = _binding_row(conn, run_id)
        if binding_row:
            existing_profile_id = str(binding_row["profile_id"] or "").strip()
            if existing_profile_id and existing_profile_id != profile_id:
                raise ValueError(
                    f"run {run_id} 已绑定到用户 {existing_profile_id}，不可归档到 {profile_id}"
                )
        bill_owner = _bill_owner_profile_id(conn, run_id)
        if bill_owner and bill_owner != profile_id:
            raise ValueError(f"run {run_id} 已归档到用户 {bill_owner}，不可归档到 {profile_id}")
        _ensure_unique_period_binding(conn, profile_id, bill)
        bill["updated_at"] = now
        if not bill.get("created_at"):
            bill["created_at"] = now
        _upsert_bill(conn, profile_id, bill)
        _upsert_run_binding_conn(conn, run_id, profile_id, now)
        conn.execute(
            "UPDATE profiles SET updated_at = ? WHERE id = ?",
            (now, profile_id),
        )

    return load_profile(root, profile_id)


def remove_bills(
    root: Path,
    profile_id: str,
    *,
    period_key: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    if not period_key and not run_id:
        raise ValueError("missing period_key or run_id")
    with _connect(root) as conn:
        _init_db(conn)
        row = conn.execute("SELECT id FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            raise FileNotFoundError(profile_id)
        if period_key and run_id:
            conn.execute(
                "DELETE FROM bills WHERE profile_id = ? AND period_key = ? AND run_id = ?",
                (profile_id, period_key, run_id),
            )
        elif period_key:
            conn.execute(
                "DELETE FROM bills WHERE profile_id = ? AND period_key = ?",
                (profile_id, period_key),
            )
        elif run_id:
            conn.execute(
                "DELETE FROM bills WHERE profile_id = ? AND run_id = ?",
                (profile_id, run_id),
            )
        conn.execute(
            "UPDATE profiles SET updated_at = ? WHERE id = ?",
            (utc_now_iso(), profile_id),
        )
    return load_profile(root, profile_id)


def reimport_bill(
    root: Path,
    profile_id: str,
    *,
    period_key: str,
    run_id: str,
) -> dict[str, Any]:
    if not period_key or not run_id:
        raise ValueError("missing period_key or run_id")
    bill = build_bill_from_run(root, run_id)
    now = utc_now_iso()

    with _connect(root) as conn:
        _init_db(conn)
        row = conn.execute("SELECT id FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            raise FileNotFoundError(profile_id)
        binding_row = _binding_row(conn, run_id)
        if binding_row:
            existing_profile_id = str(binding_row["profile_id"] or "").strip()
            if existing_profile_id and existing_profile_id != profile_id:
                raise ValueError(
                    f"run {run_id} 已绑定到用户 {existing_profile_id}，不可归档到 {profile_id}"
                )
        bill_owner = _bill_owner_profile_id(conn, run_id)
        if bill_owner and bill_owner != profile_id:
            raise ValueError(f"run {run_id} 已归档到用户 {bill_owner}，不可归档到 {profile_id}")
        conn.execute(
            "DELETE FROM bills WHERE profile_id = ? AND period_key = ?",
            (profile_id, period_key),
        )
        _ensure_unique_period_binding(conn, profile_id, bill)
        bill["updated_at"] = now
        if not bill.get("created_at"):
            bill["created_at"] = now
        _upsert_bill(conn, profile_id, bill)
        _upsert_run_binding_conn(conn, run_id, profile_id, now)
        conn.execute(
            "UPDATE profiles SET updated_at = ? WHERE id = ?",
            (now, profile_id),
        )
    return load_profile(root, profile_id)


def check_profile_integrity(root: Path, profile_id: str) -> dict[str, Any]:
    profile = load_profile(root, profile_id)
    issues: list[dict[str, Any]] = []

    for bill in profile.get("bills", []) or []:
        run_id = str(bill.get("run_id") or "")
        period_key = str(bill.get("period_key") or "")
        run_dir = root / "runs" / run_id
        if not run_dir.exists():
            issues.append(
                {
                    "run_id": run_id,
                    "period_key": period_key,
                    "issue": "missing_run_dir",
                    "path": str(run_dir),
                }
            )
            continue

        outputs = bill.get("outputs") or {}
        summary_rel = str(outputs.get("summary_csv") or "")
        categorized_rel = str(outputs.get("categorized_csv") or "")
        summary_path = (root / summary_rel) if summary_rel else run_dir / "output" / "category.summary.csv"
        categorized_path = (root / categorized_rel) if categorized_rel else run_dir / "output" / "unified.transactions.categorized.csv"

        if not summary_path.exists():
            issues.append(
                {
                    "run_id": run_id,
                    "period_key": period_key,
                    "issue": "missing_summary_csv",
                    "path": str(summary_path),
                }
            )
        elif not _csv_has_header(summary_path):
            issues.append(
                {
                    "run_id": run_id,
                    "period_key": period_key,
                    "issue": "empty_summary_csv",
                    "path": str(summary_path),
                }
            )

        if not categorized_path.exists():
            issues.append(
                {
                    "run_id": run_id,
                    "period_key": period_key,
                    "issue": "missing_categorized_csv",
                    "path": str(categorized_path),
                }
            )
        elif not _csv_has_header(categorized_path):
            issues.append(
                {
                    "run_id": run_id,
                    "period_key": period_key,
                    "issue": "empty_categorized_csv",
                    "path": str(categorized_path),
                }
            )

    return {"profile_id": profile_id, "ok": not issues, "issues": issues}
