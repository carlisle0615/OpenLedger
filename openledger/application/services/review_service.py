from __future__ import annotations

from pathlib import Path

from openledger.application.services.review_engine import build_profile_review


def build_profile_review_payload(
    root: Path,
    profile_id: str,
    *,
    year: int | None = None,
    months: int = 12,
) -> dict:
    return build_profile_review(root, profile_id, year=year, months=months)
