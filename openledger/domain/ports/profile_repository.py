from __future__ import annotations

from typing import Any, Protocol


class ProfileRepositoryPort(Protocol):
    def list_profiles(self) -> list[dict[str, Any]]: ...

    def load_profile(self, profile_id: str) -> dict[str, Any]: ...
