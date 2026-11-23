"""Domain-level exceptions.

Every business invariant violation raises a subclass of :class:`DomainError`,
so callers can distinguish domain failures from infrastructure or programming
errors.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-level errors."""


class ValidationError(DomainError):
    """Raised when a value object or entity receives invalid input."""


class InvalidBookStateError(DomainError):
    """Raised when an operation is not allowed in the book's current state."""


class LicenseViolationError(DomainError):
    """Raised when a download request breaks the book's license terms."""


class QuotaExceededError(DomainError):
    """Raised when a reader exceeds their download quota."""
