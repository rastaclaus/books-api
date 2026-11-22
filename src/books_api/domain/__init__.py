"""Pure domain layer of the books catalog."""

from books_api.domain.catalog import BookRepository, CatalogQuery, InMemoryBookRepository
from books_api.domain.download import BookDownloaded, DownloadGrant, DownloadService
from books_api.domain.entities import Author, Book, BookAsset, BookStatus
from books_api.domain.errors import (
    DomainError,
    DuplicateAssetError,
    InvalidBookStateError,
    LicenseViolationError,
    QuotaExceededError,
    ReaderSuspendedError,
    ValidationError,
)
from books_api.domain.license_policy import build_license_notice, resolve_anthology_license
from books_api.domain.reader import DailyDownloadQuota, Reader
from books_api.domain.value_objects import ISBN, BookFormat, LanguageCode, LicenseType

__all__ = [
    "ISBN",
    "Author",
    "Book",
    "BookAsset",
    "BookDownloaded",
    "BookFormat",
    "BookRepository",
    "BookStatus",
    "CatalogQuery",
    "DailyDownloadQuota",
    "DomainError",
    "DownloadGrant",
    "DownloadService",
    "DuplicateAssetError",
    "InMemoryBookRepository",
    "InvalidBookStateError",
    "LanguageCode",
    "LicenseType",
    "LicenseViolationError",
    "QuotaExceededError",
    "Reader",
    "ReaderSuspendedError",
    "ValidationError",
    "build_license_notice",
    "resolve_anthology_license",
]
