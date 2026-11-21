"""Tests for the domain error hierarchy."""

import pytest

from books_api.domain import (
    DomainError,
    InvalidBookStateError,
    LicenseViolationError,
    QuotaExceededError,
)


@pytest.mark.parametrize(
    "error_type",
    [InvalidBookStateError, LicenseViolationError, QuotaExceededError],
)
def test_specialized_error_inherits_from_domain_error(error_type: type[DomainError]) -> None:
    assert issubclass(error_type, DomainError)


@pytest.mark.parametrize(
    "error_type",
    [InvalidBookStateError, LicenseViolationError, QuotaExceededError],
)
def test_specialized_error_is_not_domain_error_itself(error_type: type[DomainError]) -> None:
    assert error_type is not DomainError


@pytest.mark.parametrize(
    "error_type",
    [InvalidBookStateError, LicenseViolationError, QuotaExceededError],
)
def test_specialized_error_preserves_message(error_type: type[DomainError]) -> None:
    message = "invariant violated"

    error = error_type(message)

    assert str(error) == message


def test_domain_error_can_be_raised_and_caught() -> None:
    with pytest.raises(DomainError, match="quota exceeded"):
        raise QuotaExceededError("quota exceeded")
