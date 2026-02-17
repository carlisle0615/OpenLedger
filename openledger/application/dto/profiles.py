from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProfileBinding:
    run_id: str
    profile_id: str
    created_at: str
    updated_at: str
