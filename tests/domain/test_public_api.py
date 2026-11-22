"""Tests for the public API of the domain package."""

from books_api import domain


def test_domain_package_exports_errors() -> None:
    assert domain.__all__ == [
        "ISBN",
        "BookFormat",
        "DomainError",
        "InvalidBookStateError",
        "LanguageCode",
        "LicenseType",
        "LicenseViolationError",
        "QuotaExceededError",
        "ValidationError",
    ]


def test_exported_names_resolve_to_error_classes() -> None:
    assert domain.DomainError.__name__ == "DomainError"
    assert domain.InvalidBookStateError.__name__ == "InvalidBookStateError"
    assert domain.LicenseViolationError.__name__ == "LicenseViolationError"
    assert domain.QuotaExceededError.__name__ == "QuotaExceededError"
    assert domain.ValidationError.__name__ == "ValidationError"
    assert domain.BookFormat.__name__ == "BookFormat"
    assert domain.LanguageCode.__name__ == "LanguageCode"
    assert domain.ISBN.__name__ == "ISBN"
    assert domain.LicenseType.__name__ == "LicenseType"
