"""Domain-level exception hierarchy.

Every violation of a business invariant is reported with a subclass of
``DomainError`` so callers can distinguish domain failures from programming
errors and infrastructure failures.
"""


class DomainError(Exception):
    """Base class for all domain invariant violations."""


class InvalidBookStateError(DomainError):
    """Raised when an operation is not allowed for the current book state."""


class LicenseViolationError(DomainError):
    """Raised when an operation would violate a book's license terms."""


class QuotaExceededError(DomainError):
    """Raised when an operation would exceed an applicable quota."""
