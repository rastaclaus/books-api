"""Domain event, grant and service for free e-book downloads."""

import re
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from books_api.domain._checks import ensure_iterable, ensure_required_text, ensure_str
from books_api.domain.entities import Book, BookAsset
from books_api.domain.errors import InvalidBookStateError, ValidationError
from books_api.domain.license_policy import build_license_notice
from books_api.domain.reader import Reader
from books_api.domain.value_objects import BookFormat

_SHA256_HEX_LENGTH = 64
_SHA256_PATTERN = re.compile(rf"[0-9a-f]{{{_SHA256_HEX_LENGTH}}}")


@dataclass(frozen=True, slots=True)
class BookDownloaded:
    """Domain event recorded when a reader downloads a book."""

    book_id: str
    reader_id: str
    format: BookFormat
    occurred_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "book_id", ensure_required_text(self.book_id, "Book id"))
        object.__setattr__(self, "reader_id", ensure_required_text(self.reader_id, "Reader id"))

        if not isinstance(self.format, BookFormat):
            raise ValidationError("Download format must be a BookFormat member")
        if not isinstance(self.occurred_at, datetime):
            raise ValidationError("Download timestamp must be a datetime")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValidationError("Download timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class DownloadGrant:
    """Immutable outcome of a permitted download request."""

    book_id: str
    reader_id: str
    format: BookFormat
    checksum: str
    license_notice: str
    event: BookDownloaded
    quota_consumed: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "book_id", ensure_required_text(self.book_id, "Book id"))
        object.__setattr__(self, "reader_id", ensure_required_text(self.reader_id, "Reader id"))
        object.__setattr__(self, "checksum", _normalize_checksum(self.checksum))
        object.__setattr__(self, "license_notice", ensure_required_text(self.license_notice, "License notice"))

        if not isinstance(self.format, BookFormat):
            raise ValidationError("Download format must be a BookFormat member")
        if not isinstance(self.quota_consumed, bool):
            raise ValidationError("Quota consumed flag must be a boolean")
        if not isinstance(self.event, BookDownloaded):
            raise ValidationError("Download grant requires a BookDownloaded event")

        event_identity = (self.event.book_id, self.event.reader_id, self.event.format)
        grant_identity = (self.book_id, self.reader_id, self.format)
        if event_identity != grant_identity:
            raise ValidationError("Download event must match the grant book, reader and format")


@dataclass(frozen=True, slots=True)
class DownloadService:
    """Stateless domain service authorizing and describing downloads."""

    def request_download(
        self,
        book: Book,
        reader: Reader,
        fmt: BookFormat,
        downloaded_today: Collection[str],
        now: datetime,
    ) -> DownloadGrant:
        """Return a grant for a permitted download or raise a domain error."""
        self._validate_arguments(book, reader, fmt, downloaded_today, now)
        downloaded_ids = _normalize_downloaded_ids(downloaded_today)

        if not book.is_downloadable:
            raise InvalidBookStateError(f"Book {book.id!r} is not available for download")

        asset = _find_asset(book, fmt)
        reader.check_download_allowed(book.id, downloaded_today=downloaded_ids)

        quota_consumed = book.id not in downloaded_ids
        event = BookDownloaded(book_id=book.id, reader_id=reader.id, format=fmt, occurred_at=now)
        return DownloadGrant(
            book_id=book.id,
            reader_id=reader.id,
            format=fmt,
            checksum=asset.checksum,
            license_notice=build_license_notice(book),
            event=event,
            quota_consumed=quota_consumed,
        )

    @staticmethod
    def _validate_arguments(
        book: object,
        reader: object,
        fmt: object,
        downloaded_today: object,
        now: object,
    ) -> None:
        if not isinstance(book, Book):
            raise ValidationError("Download request requires a Book instance")
        if not isinstance(reader, Reader):
            raise ValidationError("Download request requires a Reader instance")
        if not isinstance(fmt, BookFormat):
            raise ValidationError("Download request format must be a BookFormat member")
        if not isinstance(downloaded_today, Collection):
            raise ValidationError("Downloaded book ids must be a collection of book ids")
        if not isinstance(now, datetime):
            raise ValidationError("Download request timestamp must be a datetime")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValidationError("Download request timestamp must be timezone-aware")


def _normalize_downloaded_ids(downloaded_today: Collection[str]) -> frozenset[str]:
    raw_ids = ensure_iterable(
        downloaded_today,
        "Downloaded book ids must be a collection of book ids, not a string",
    )
    return frozenset(ensure_required_text(book_id, "Downloaded book id") for book_id in raw_ids)


def _find_asset(book: Book, fmt: BookFormat) -> BookAsset:
    for asset in book.assets:
        if asset.format is fmt:
            return asset
    raise InvalidBookStateError(f"Book {book.id!r} has no asset in {fmt.value} format")


def _normalize_checksum(checksum: object) -> str:
    normalized_checksum = ensure_str(checksum, "Download checksum must be a string").strip().lower()
    if _SHA256_PATTERN.fullmatch(normalized_checksum) is None:
        raise ValidationError("Download checksum must be a 64-character SHA-256 hex digest")
    return normalized_checksum
