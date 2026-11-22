"""Tests for the public API of the domain package."""

from books_api import domain


def test_domain_package_exports_errors() -> None:
    assert domain.__all__ == [
        "ISBN",
        "Author",
        "Book",
        "BookAsset",
        "BookFormat",
        "BookStatus",
        "DailyDownloadQuota",
        "DomainError",
        "DuplicateAssetError",
        "InvalidBookStateError",
        "LanguageCode",
        "LicenseType",
        "LicenseViolationError",
        "QuotaExceededError",
        "Reader",
        "ReaderSuspendedError",
        "ValidationError",
    ]


def test_exported_names_resolve_to_error_classes() -> None:
    assert domain.DomainError.__name__ == "DomainError"
    assert domain.DuplicateAssetError.__name__ == "DuplicateAssetError"
    assert domain.InvalidBookStateError.__name__ == "InvalidBookStateError"
    assert domain.LicenseViolationError.__name__ == "LicenseViolationError"
    assert domain.QuotaExceededError.__name__ == "QuotaExceededError"
    assert domain.ReaderSuspendedError.__name__ == "ReaderSuspendedError"
    assert domain.ValidationError.__name__ == "ValidationError"
    assert domain.Author.__name__ == "Author"
    assert domain.Book.__name__ == "Book"
    assert domain.BookAsset.__name__ == "BookAsset"
    assert domain.BookFormat.__name__ == "BookFormat"
    assert domain.BookStatus.__name__ == "BookStatus"
    assert domain.DailyDownloadQuota.__name__ == "DailyDownloadQuota"
    assert domain.LanguageCode.__name__ == "LanguageCode"
    assert domain.ISBN.__name__ == "ISBN"
    assert domain.LicenseType.__name__ == "LicenseType"
    assert domain.Reader.__name__ == "Reader"
