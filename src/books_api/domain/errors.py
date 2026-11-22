"""Domain-level exception hierarchy.

Every violation of a business invariant is reported with a subclass of
``DomainError`` so callers can distinguish domain failures from programming
errors and infrastructure failures.
"""


class DomainError(Exception):
    """Base class for all domain invariant violations."""


class DuplicateAssetError(DomainError):
    """Raised when a book already has an asset in the requested format."""


class InvalidBookStateError(DomainError):
    """Raised when an operation is not allowed for the current book state."""


class LicenseViolationError(DomainError):
    """Raised when an operation would violate a book's license terms."""


class QuotaExceededError(DomainError):
    """Raised when an operation would exceed an applicable quota."""


class ValidationError(DomainError):
    """Raised when a value violates the invariants of its domain type."""
