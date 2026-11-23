from __future__ import annotations

import pytest

from books_api.domain import (
    DomainError,
    InvalidBookStateError,
    LicenseViolationError,
    QuotaExceededError,
    ValidationError,
)

SPECIALIZED_ERRORS = [
    ValidationError,
    InvalidBookStateError,
    LicenseViolationError,
    QuotaExceededError,
]


def test_domain_error_is_an_exception() -> None:
    assert issubclass(DomainError, Exception)


@pytest.mark.parametrize("error_type", SPECIALIZED_ERRORS)
def test_specialized_errors_inherit_from_domain_error(error_type: type[DomainError]) -> None:
    assert issubclass(error_type, DomainError)


@pytest.mark.parametrize("error_type", SPECIALIZED_ERRORS)
def test_errors_keep_message(error_type: type[DomainError]) -> None:
    error = error_type("license forbids commercial reuse")

    assert str(error) == "license forbids commercial reuse"


def test_specialized_errors_are_distinct() -> None:
    assert len(set(SPECIALIZED_ERRORS)) == len(SPECIALIZED_ERRORS)
    assert DomainError not in SPECIALIZED_ERRORS


def test_errors_can_be_caught_as_domain_error() -> None:
    with pytest.raises(DomainError):
        raise QuotaExceededError("daily quota of 5 downloads exceeded")
