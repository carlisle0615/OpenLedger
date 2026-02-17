from __future__ import annotations

from pathlib import Path
from typing import Any

from openledger.infrastructure.persistence.sqla.profile_store import (
    add_bill_from_run,
    check_profile_integrity,
    clear_run_binding,
    create_profile,
    get_run_binding,
    list_profiles,
    load_profile,
    remove_bills,
    reimport_bill,
    set_run_binding,
    update_profile,
)


def list_profiles_payload(root: Path) -> dict[str, Any]:
    return {"profiles": list_profiles(root)}


def create_profile_payload(root: Path, *, name: str) -> dict[str, Any]:
    return create_profile(root, name)


def get_profile_payload(root: Path, profile_id: str) -> dict[str, Any]:
    return load_profile(root, profile_id)


def update_profile_payload(
    root: Path, profile_id: str, updates: dict[str, Any]
) -> dict[str, Any]:
    return update_profile(root, profile_id, updates)


def check_profile_payload(root: Path, profile_id: str) -> dict[str, Any]:
    return check_profile_integrity(root, profile_id)


def add_bill_payload(
    root: Path,
    profile_id: str,
    *,
    run_id: str,
    period_year: int | None = None,
    period_month: int | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, int | None] = {}
    if period_year is not None or period_month is not None:
        kwargs["period_year"] = period_year
        kwargs["period_month"] = period_month
    return add_bill_from_run(root, profile_id, run_id, **kwargs)


def remove_bill_payload(
    root: Path,
    profile_id: str,
    *,
    period_key: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    return remove_bills(root, profile_id, period_key=period_key, run_id=run_id)


def reimport_bill_payload(
    root: Path,
    profile_id: str,
    *,
    period_key: str,
    run_id: str,
) -> dict[str, Any]:
    return reimport_bill(root, profile_id, period_key=period_key, run_id=run_id)


def get_run_binding_payload(root: Path, run_id: str) -> dict[str, Any] | None:
    return get_run_binding(root, run_id)


def set_run_binding_payload(root: Path, run_id: str, profile_id: str) -> dict[str, Any]:
    return set_run_binding(root, run_id, profile_id)


def clear_run_binding_payload(root: Path, run_id: str) -> None:
    clear_run_binding(root, run_id)
