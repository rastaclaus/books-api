"""Tests for the download domain event, grant and service."""

from collections.abc import Collection
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime
from typing import cast

import pytest

from books_api.domain import (
    Author,
    Book,
    BookAsset,
    BookFormat,
    BookStatus,
    DomainError,
    InvalidBookStateError,
    LanguageCode,
    LicenseType,
    QuotaExceededError,
    Reader,
    ReaderSuspendedError,
    ValidationError,
)
from books_api.domain.download import BookDownloaded, DownloadGrant, DownloadService

_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
_EPUB_CHECKSUM = "a" * 64
_PDF_CHECKSUM = "b" * 64
_ADA = Author(id="author-1", full_name="Ada Lovelace")
_GRACE = Author(id="author-2", full_name="Grace Hopper")
_EPUB_ASSET = BookAsset(format=BookFormat.EPUB, size_bytes=1024, checksum=_EPUB_CHECKSUM)
_PDF_ASSET = BookAsset(format=BookFormat.PDF, size_bytes=2048, checksum=_PDF_CHECKSUM)
_BLANK_STRINGS = ["", " ", "\t\n", "\u00a0", "\u2003", "\u3000", "\u2028", "\u200b", "\ufeff"]
_DEFAULT = object()


def make_book(
    *,
    book_id: str = "book-1",
    status: BookStatus = BookStatus.PUBLISHED,
    license_type: LicenseType = LicenseType.CC_BY,
    authors: tuple[Author, ...] = (_ADA,),
    assets: tuple[BookAsset, ...] = (_EPUB_ASSET,),
) -> Book:
    return Book(
        id=book_id,
        title="Structure and Interpretation",
        language=LanguageCode("en"),
        license=license_type,
        authors=authors,
        status=status,
        assets=assets,
        withdrawal_reason="Rights expired" if status is BookStatus.WITHDRAWN else None,
    )


def make_reader(
    *,
    reader_id: str = "reader-1",
    is_verified: bool = False,
    is_suspended: bool = False,
) -> Reader:
    return Reader(id=reader_id, is_verified=is_verified, is_suspended=is_suspended)


def make_downloaded_ids(count: int) -> tuple[str, ...]:
    return tuple(f"other-book-{index}" for index in range(count))


def make_event(
    *,
    book_id: str = "book-1",
    reader_id: str = "reader-1",
    book_format: BookFormat = BookFormat.EPUB,
) -> BookDownloaded:
    return BookDownloaded(book_id=book_id, reader_id=reader_id, format=book_format, occurred_at=_NOW)


def make_grant() -> DownloadGrant:
    return DownloadGrant(
        book_id="book-1",
        reader_id="reader-1",
        format=BookFormat.EPUB,
        checksum=_EPUB_CHECKSUM,
        license_notice="Licensed under CC BY 4.0.",
        event=make_event(),
        quota_consumed=True,
    )


def call_request_download(
    *,
    book: object = _DEFAULT,
    reader: object = _DEFAULT,
    fmt: object = _DEFAULT,
    downloaded_today: object = _DEFAULT,
    now: object = _DEFAULT,
) -> DownloadGrant:
    return DownloadService().request_download(
        cast("Book", make_book() if book is _DEFAULT else book),
        cast("Reader", make_reader() if reader is _DEFAULT else reader),
        cast("BookFormat", BookFormat.EPUB if fmt is _DEFAULT else fmt),
        cast("Collection[str]", [] if downloaded_today is _DEFAULT else downloaded_today),
        cast("datetime", _NOW if now is _DEFAULT else now),
    )


def test_request_download_returns_full_grant() -> None:
    grant = DownloadService().request_download(make_book(), make_reader(), BookFormat.EPUB, [], _NOW)

    assert grant.book_id == "book-1"
    assert grant.reader_id == "reader-1"
    assert grant.format is BookFormat.EPUB
    assert grant.checksum == _EPUB_CHECKSUM
    assert grant.license_notice == "Licensed under CC BY 4.0. Attribution to Ada Lovelace is required."
    assert grant.quota_consumed is True
    assert grant.event == BookDownloaded(
        book_id="book-1",
        reader_id="reader-1",
        format=BookFormat.EPUB,
        occurred_at=_NOW,
    )


def test_request_download_selects_the_requested_format_asset() -> None:
    book = make_book(assets=(_EPUB_ASSET, _PDF_ASSET))

    grant = DownloadService().request_download(book, make_reader(), BookFormat.PDF, (), _NOW)

    assert grant.format is BookFormat.PDF
    assert grant.checksum == _PDF_CHECKSUM
    assert grant.event.format is BookFormat.PDF


def test_request_download_normalizes_grant_and_event_identifiers() -> None:
    grant = DownloadService().request_download(
        make_book(book_id="  book-1  "),
        make_reader(reader_id="  reader-1  "),
        BookFormat.EPUB,
        (),
        _NOW,
    )

    assert grant.book_id == "book-1"
    assert grant.reader_id == "reader-1"
    assert grant.event.book_id == "book-1"
    assert grant.event.reader_id == "reader-1"
    assert grant.event.occurred_at is _NOW


def test_new_book_consumes_quota() -> None:
    reader = make_reader()
    downloaded_today = make_downloaded_ids(reader.daily_download_limit - 1)

    grant = DownloadService().request_download(make_book(), reader, BookFormat.EPUB, downloaded_today, _NOW)

    assert grant.quota_consumed is True


@pytest.mark.parametrize(
    "downloaded_today",
    [
        ("book-1",),
        ("  book-1  ",),
        ("other-book-0", "book-1", "other-book-2"),
    ],
)
def test_redownload_same_day_does_not_consume_quota(*, downloaded_today: tuple[str, ...]) -> None:
    reader = make_reader()

    grant = DownloadService().request_download(make_book(), reader, BookFormat.EPUB, downloaded_today, _NOW)

    assert grant.quota_consumed is False


def test_redownload_succeeds_even_when_quota_is_exhausted() -> None:
    reader = make_reader()
    downloaded_today = (*make_downloaded_ids(reader.daily_download_limit - 1), "book-1")

    grant = DownloadService().request_download(make_book(), reader, BookFormat.EPUB, downloaded_today, _NOW)

    assert grant.quota_consumed is False


@pytest.mark.parametrize("status", [BookStatus.DRAFT, BookStatus.WITHDRAWN])
def test_request_download_rejects_unavailable_book(*, status: BookStatus) -> None:
    with pytest.raises(InvalidBookStateError, match="not available for download"):
        DownloadService().request_download(make_book(status=status), make_reader(), BookFormat.EPUB, (), _NOW)


@pytest.mark.parametrize("status", [BookStatus.DRAFT, BookStatus.WITHDRAWN])
def test_unavailable_book_error_is_a_domain_error(*, status: BookStatus) -> None:
    with pytest.raises(DomainError):
        DownloadService().request_download(make_book(status=status), make_reader(), BookFormat.EPUB, (), _NOW)


def test_request_download_rejects_book_without_requested_format() -> None:
    book = make_book(assets=(_EPUB_ASSET,))

    with pytest.raises(InvalidBookStateError, match="no asset in pdf format"):
        DownloadService().request_download(book, make_reader(), BookFormat.PDF, (), _NOW)


@pytest.mark.parametrize("downloaded_today", [(), ("book-1",)])
def test_request_download_rejects_suspended_reader(*, downloaded_today: tuple[str, ...]) -> None:
    reader = make_reader(is_suspended=True)

    with pytest.raises(ReaderSuspendedError, match="suspended"):
        DownloadService().request_download(make_book(), reader, BookFormat.EPUB, downloaded_today, _NOW)


@pytest.mark.parametrize("is_verified", [False, True])
def test_request_download_rejects_exhausted_quota(*, is_verified: bool) -> None:
    reader = make_reader(is_verified=is_verified)
    downloaded_today = make_downloaded_ids(reader.daily_download_limit)

    with pytest.raises(QuotaExceededError, match="daily download limit"):
        DownloadService().request_download(make_book(), reader, BookFormat.EPUB, downloaded_today, _NOW)


@pytest.mark.parametrize(
    ("license_type", "expected"),
    [
        (LicenseType.PUBLIC_DOMAIN, "This work is in the public domain."),
        (LicenseType.CC0, "Dedicated to the public domain under CC0 1.0 Universal."),
        (LicenseType.CC_BY, "Licensed under CC BY 4.0. Attribution to Ada Lovelace is required."),
        (
            LicenseType.CC_BY_SA,
            "Licensed under CC BY-SA 4.0. Attribution to Ada Lovelace and ShareAlike required.",
        ),
    ],
)
def test_request_download_builds_license_notice(*, license_type: LicenseType, expected: str) -> None:
    grant = DownloadService().request_download(
        make_book(license_type=license_type),
        make_reader(),
        BookFormat.EPUB,
        (),
        _NOW,
    )

    assert grant.license_notice == expected


def test_cc_by_notice_contains_every_author_full_name() -> None:
    book = make_book(license_type=LicenseType.CC_BY, authors=(_ADA, _GRACE))

    grant = DownloadService().request_download(book, make_reader(), BookFormat.EPUB, (), _NOW)

    assert "Ada Lovelace" in grant.license_notice
    assert "Grace Hopper" in grant.license_notice


def test_book_downloaded_is_frozen_and_slotted() -> None:
    event = make_event()
    event_attribute = "book_id"

    with pytest.raises(FrozenInstanceError):
        setattr(event, event_attribute, "book-2")

    assert not hasattr(event, "__dict__")


def test_download_grant_is_frozen_and_slotted() -> None:
    grant = make_grant()
    grant_attribute = "checksum"

    with pytest.raises(FrozenInstanceError):
        setattr(grant, grant_attribute, _PDF_CHECKSUM)

    assert not hasattr(grant, "__dict__")


@pytest.mark.parametrize("field", ["book_id", "reader_id"])
@pytest.mark.parametrize("value", _BLANK_STRINGS)
def test_book_downloaded_rejects_blank_identifiers(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match="visible characters"):
        replace(make_event(), **{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("book_id", 1),
        ("book_id", None),
        ("reader_id", 1),
        ("reader_id", None),
    ],
)
def test_book_downloaded_rejects_non_text_identifiers(field: str, value: object) -> None:
    with pytest.raises(ValidationError, match="must be a string"):
        replace(make_event(), **{field: value})


@pytest.mark.parametrize("book_format", ["epub", None, 1])
def test_book_downloaded_rejects_non_book_format(book_format: object) -> None:
    with pytest.raises(ValidationError, match="BookFormat"):
        replace(make_event(), format=book_format)


@pytest.mark.parametrize("occurred_at", ["2026-01-15", date(2026, 1, 15), None, 0])
def test_book_downloaded_rejects_non_datetime_timestamp(occurred_at: object) -> None:
    with pytest.raises(ValidationError, match="timestamp"):
        replace(make_event(), occurred_at=occurred_at)


@pytest.mark.parametrize("checksum", [*_BLANK_STRINGS, None, 1])
def test_download_grant_rejects_blank_or_non_text_checksum(checksum: object) -> None:
    with pytest.raises(ValidationError, match="checksum"):
        replace(make_grant(), checksum=checksum)


@pytest.mark.parametrize("license_notice", [*_BLANK_STRINGS, None, 1])
def test_download_grant_rejects_blank_or_non_text_license_notice(license_notice: object) -> None:
    with pytest.raises(ValidationError, match="notice"):
        replace(make_grant(), license_notice=license_notice)


@pytest.mark.parametrize("quota_consumed", [1, 0, "yes", None])
def test_download_grant_rejects_non_boolean_quota_flag(quota_consumed: object) -> None:
    with pytest.raises(ValidationError, match="boolean"):
        replace(make_grant(), quota_consumed=quota_consumed)


@pytest.mark.parametrize("event", [None, "event", object()])
def test_download_grant_rejects_non_event(event: object) -> None:
    with pytest.raises(ValidationError, match="BookDownloaded event"):
        replace(make_grant(), event=cast("BookDownloaded", event))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("book_id", "book-2"),
        ("reader_id", "reader-2"),
        ("format", BookFormat.PDF),
    ],
)
def test_download_grant_rejects_event_that_does_not_match(field: str, value: object) -> None:
    grant = make_grant()

    with pytest.raises(ValidationError, match="must match"):
        replace(grant, event=replace(grant.event, **{field: value}))


@pytest.mark.parametrize("field", ["book_id", "reader_id"])
def test_download_grant_rejects_blank_identifiers(field: str) -> None:
    with pytest.raises(ValidationError, match="visible characters"):
        replace(make_grant(), **{field: "  "})


@pytest.mark.parametrize(
    ("argument", "value", "message"),
    [
        ("book", "book", "Book instance"),
        ("book", None, "Book instance"),
        ("reader", "reader", "Reader instance"),
        ("reader", None, "Reader instance"),
        ("fmt", "epub", "BookFormat"),
        ("fmt", None, "BookFormat"),
        ("downloaded_today", "book-1", "not a string"),
        ("downloaded_today", None, "collection"),
        ("downloaded_today", 42, "collection"),
        ("now", "2026-01-15", "datetime"),
        ("now", date(2026, 1, 15), "datetime"),
        ("now", None, "datetime"),
    ],
)
def test_request_download_rejects_invalid_arguments(argument: str, value: object, message: str) -> None:
    kwargs: dict[str, object] = {argument: value}

    with pytest.raises(ValidationError, match=message):
        call_request_download(**kwargs)


@pytest.mark.parametrize(
    ("downloaded_today", "message"),
    [
        ([1], "must be a string"),
        ([None], "must be a string"),
        (["  "], "visible characters"),
    ],
)
def test_request_download_rejects_invalid_downloaded_book_ids(
    *,
    downloaded_today: list[object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        call_request_download(downloaded_today=downloaded_today)


def test_book_downloaded_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        replace(make_event(), occurred_at=_NOW.replace(tzinfo=None))


def test_request_download_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        call_request_download(now=_NOW.replace(tzinfo=None))


def test_download_grant_normalizes_checksum() -> None:
    grant = replace(make_grant(), checksum=f"  {_EPUB_CHECKSUM.upper()}  ")

    assert grant.checksum == _EPUB_CHECKSUM


@pytest.mark.parametrize("checksum", ["a" * 63, "a" * 65, "g" * 64, f"{'a' * 63}z"])
def test_download_grant_rejects_malformed_checksum(checksum: str) -> None:
    with pytest.raises(ValidationError, match="SHA-256"):
        replace(make_grant(), checksum=checksum)
