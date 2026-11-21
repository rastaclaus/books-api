"""Pure domain layer of the books catalog."""

from books_api.domain.errors import (
    DomainError,
    InvalidBookStateError,
    LicenseViolationError,
    QuotaExceededError,
)

__all__ = [
    "DomainError",
    "InvalidBookStateError",
    "LicenseViolationError",
    "QuotaExceededError",
]
