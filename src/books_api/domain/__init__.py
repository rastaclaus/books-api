"""Pure domain layer of the books catalog."""

from __future__ import annotations

from books_api.domain.errors import (
    DomainError,
    InvalidBookStateError,
    LicenseViolationError,
    QuotaExceededError,
    ValidationError,
)

__all__ = [
    "DomainError",
    "InvalidBookStateError",
    "LicenseViolationError",
    "QuotaExceededError",
    "ValidationError",
]
