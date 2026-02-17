from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class DomainError(Exception):
    code: str
    message: str
    details: Any = None
    status_code: int = 400

    def __str__(self) -> str:
        return self.message


class NotFoundError(DomainError):
    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(
            code="not_found",
            message=message,
            details=details,
            status_code=404,
        )


class ConflictError(DomainError):
    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(
            code="conflict",
            message=message,
            details=details,
            status_code=409,
        )


class ValidationError(DomainError):
    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(
            code="validation_error",
            message=message,
            details=details,
            status_code=400,
        )
