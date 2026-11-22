"""Tests for the reader entity and the daily anti-bot download quota."""

from dataclasses import FrozenInstanceError, replace

import pytest

from books_api.domain import (
    DailyDownloadQuota,
    QuotaExceededError,
    Reader,
    ReaderSuspendedError,
    ValidationError,
)

_UNVERIFIED_DAILY_DOWNLOAD_LIMIT = 3
_VERIFIED_DAILY_DOWNLOAD_LIMIT = 25
_BLANK_STRINGS = ["", " ", "\t\n", "\u00a0", "\u2003", "\u3000", "\u2028", "\u200b", "\ufeff"]


def make_reader(
    *,
    reader_id: str = "reader-1",
    is_verified: bool = False,
    is_suspended: bool = False,
) -> Reader:
    return Reader(id=reader_id, is_verified=is_verified, is_suspended=is_suspended)


def make_downloaded_ids(count: int) -> tuple[str, ...]:
    return tuple(f"book-{index}" for index in range(count))


@pytest.mark.parametrize(
    ("is_verified", "expected_limit"),
    [
        (False, _UNVERIFIED_DAILY_DOWNLOAD_LIMIT),
        (True, _VERIFIED_DAILY_DOWNLOAD_LIMIT),
    ],
)
def test_reader_exposes_daily_download_limit(*, is_verified: bool, expected_limit: int) -> None:
    reader = make_reader(is_verified=is_verified)

    assert reader.daily_download_limit == expected_limit


def test_reader_defaults_to_unverified_and_active() -> None:
    reader = Reader(id="reader-1")

    assert reader.is_verified is False
    assert reader.is_suspended is False
    assert reader.daily_download_limit == _UNVERIFIED_DAILY_DOWNLOAD_LIMIT


def test_reader_normalizes_id() -> None:
    reader = make_reader(reader_id="  reader-1  ")

    assert reader.id == "reader-1"


@pytest.mark.parametrize("reader_id", _BLANK_STRINGS)
def test_reader_rejects_empty_id(reader_id: str) -> None:
    with pytest.raises(ValidationError, match="Reader id"):
        make_reader(reader_id=reader_id)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("id", 1, "Reader id must be a string"),
        ("id", None, "Reader id must be a string"),
        ("is_verified", 1, "is_verified flag must be a boolean"),
        ("is_suspended", "yes", "is_suspended flag must be a boolean"),
    ],
)
def test_reader_rejects_invalid_field_types(field: str, value: object, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        replace(make_reader(), **{field: value})


def test_reader_and_quota_are_frozen_and_slotted() -> None:
    reader = make_reader()
    reader_attribute = "is_verified"
    quota = DailyDownloadQuota(limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT)
    quota_attribute = "limit"

    with pytest.raises(FrozenInstanceError):
        setattr(reader, reader_attribute, True)
    with pytest.raises(FrozenInstanceError):
        setattr(quota, quota_attribute, _VERIFIED_DAILY_DOWNLOAD_LIMIT)

    assert not hasattr(reader, "__dict__")
    assert not hasattr(quota, "__dict__")


def test_reader_builds_quota_for_today() -> None:
    reader = make_reader()

    quota = reader.quota_for_today([" book-1 ", "book-2"])

    assert quota.limit == _UNVERIFIED_DAILY_DOWNLOAD_LIMIT
    assert quota.used == 2
    assert quota.remaining == 1
    assert quota.downloaded_book_ids == frozenset({"book-1", "book-2"})


def test_reader_quota_for_today_copies_mutable_downloaded_ids() -> None:
    downloaded_book_ids = ["book-1"]

    quota = make_reader().quota_for_today(downloaded_book_ids)
    downloaded_book_ids.append("book-2")

    assert quota.downloaded_book_ids == frozenset({"book-1"})


def test_quota_normalizes_and_deduplicates_downloaded_book_ids() -> None:
    quota = DailyDownloadQuota(
        limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT,
        downloaded_book_ids=frozenset({" book-1 ", "book-1", "book-2"}),
    )

    assert quota.downloaded_book_ids == frozenset({"book-1", "book-2"})
    assert quota.used == 2


def test_quota_copies_downloaded_ids_from_a_mutable_collection() -> None:
    downloaded_book_ids = ["book-1"]

    quota = replace(
        DailyDownloadQuota(limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT),
        downloaded_book_ids=downloaded_book_ids,
    )
    downloaded_book_ids.append("book-2")

    assert quota.downloaded_book_ids == frozenset({"book-1"})


def test_quota_remaining_never_becomes_negative() -> None:
    quota = DailyDownloadQuota(
        limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT,
        downloaded_book_ids=frozenset(make_downloaded_ids(5)),
    )

    assert quota.remaining == 0


@pytest.mark.parametrize("downloaded_count", range(_UNVERIFIED_DAILY_DOWNLOAD_LIMIT))
def test_unverified_quota_allows_new_book_below_limit(downloaded_count: int) -> None:
    quota = DailyDownloadQuota(
        limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT,
        downloaded_book_ids=frozenset(make_downloaded_ids(downloaded_count)),
    )

    assert quota.allows("new-book") is True


def test_quota_rejects_new_book_at_limit() -> None:
    quota = DailyDownloadQuota(
        limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT,
        downloaded_book_ids=frozenset(make_downloaded_ids(_UNVERIFIED_DAILY_DOWNLOAD_LIMIT)),
    )

    assert quota.allows("new-book") is False


def test_quota_allows_repeated_book_at_limit() -> None:
    quota = DailyDownloadQuota(
        limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT,
        downloaded_book_ids=frozenset(make_downloaded_ids(_UNVERIFIED_DAILY_DOWNLOAD_LIMIT)),
    )

    assert quota.allows("book-0") is True


def test_quota_register_returns_updated_snapshot_without_mutating_original() -> None:
    quota = DailyDownloadQuota(limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT)

    updated = quota.register("  book-1  ")

    assert updated.downloaded_book_ids == frozenset({"book-1"})
    assert updated.remaining == _UNVERIFIED_DAILY_DOWNLOAD_LIMIT - 1
    assert quota.downloaded_book_ids == frozenset()


def test_quota_register_keeps_existing_book_as_single_entry() -> None:
    quota = DailyDownloadQuota(
        limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT,
        downloaded_book_ids=frozenset({"book-1"}),
    )

    updated = quota.register(" book-1 ")

    assert updated.downloaded_book_ids == frozenset({"book-1"})
    assert updated.used == 1


def test_quota_register_rejects_new_book_when_limit_is_reached() -> None:
    quota = DailyDownloadQuota(
        limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT,
        downloaded_book_ids=frozenset(make_downloaded_ids(_UNVERIFIED_DAILY_DOWNLOAD_LIMIT)),
    )

    with pytest.raises(QuotaExceededError, match="Daily download limit"):
        quota.register("new-book")


def test_quota_register_allows_repeat_when_limit_is_reached() -> None:
    downloaded_book_ids = make_downloaded_ids(_UNVERIFIED_DAILY_DOWNLOAD_LIMIT)
    quota = DailyDownloadQuota(
        limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT,
        downloaded_book_ids=frozenset(downloaded_book_ids),
    )

    updated = quota.register(downloaded_book_ids[0])

    assert updated.downloaded_book_ids == quota.downloaded_book_ids
    assert updated.used == _UNVERIFIED_DAILY_DOWNLOAD_LIMIT


@pytest.mark.parametrize("limit", [0, -1, -25])
def test_quota_rejects_non_positive_limit(limit: int) -> None:
    with pytest.raises(ValidationError, match="positive"):
        DailyDownloadQuota(limit=limit)


@pytest.mark.parametrize("limit", [1.0, True, "3", None])
def test_quota_rejects_non_integer_limit(limit: object) -> None:
    with pytest.raises(ValidationError, match="positive integer"):
        replace(DailyDownloadQuota(limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT), limit=limit)


@pytest.mark.parametrize("downloaded_book_ids", ["book-1", None, 1])
def test_quota_rejects_non_iterable_downloaded_ids(downloaded_book_ids: object) -> None:
    with pytest.raises(ValidationError, match="iterable of book ids"):
        replace(
            DailyDownloadQuota(limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT),
            downloaded_book_ids=downloaded_book_ids,
        )


def test_quota_rejects_non_string_downloaded_book_id() -> None:
    with pytest.raises(ValidationError, match="Book id must be a string"):
        replace(
            DailyDownloadQuota(limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT),
            downloaded_book_ids=frozenset({1}),
        )


@pytest.mark.parametrize("book_id", _BLANK_STRINGS)
def test_quota_rejects_empty_downloaded_book_id(book_id: str) -> None:
    with pytest.raises(ValidationError, match="Book id"):
        DailyDownloadQuota(limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT, downloaded_book_ids=frozenset({book_id}))


@pytest.mark.parametrize("book_id", _BLANK_STRINGS)
def test_quota_rejects_empty_book_id_in_allows_and_register(book_id: str) -> None:
    quota = DailyDownloadQuota(limit=_UNVERIFIED_DAILY_DOWNLOAD_LIMIT)

    with pytest.raises(ValidationError, match="Book id"):
        quota.allows(book_id)
    with pytest.raises(ValidationError, match="Book id"):
        quota.register(book_id)


@pytest.mark.parametrize("downloaded_count", range(_UNVERIFIED_DAILY_DOWNLOAD_LIMIT))
def test_unverified_reader_can_download_within_quota(downloaded_count: int) -> None:
    reader = make_reader()
    downloaded_today = make_downloaded_ids(downloaded_count)

    reader.check_download_allowed("new-book", downloaded_today=downloaded_today)


def test_unverified_reader_is_denied_new_book_after_three_distinct_downloads() -> None:
    reader = make_reader()
    downloaded_today = make_downloaded_ids(_UNVERIFIED_DAILY_DOWNLOAD_LIMIT)

    with pytest.raises(QuotaExceededError, match="daily download limit"):
        reader.check_download_allowed("new-book", downloaded_today=downloaded_today)


def test_unverified_reader_may_repeat_book_at_quota_limit() -> None:
    reader = make_reader()
    downloaded_today = make_downloaded_ids(_UNVERIFIED_DAILY_DOWNLOAD_LIMIT)

    reader.check_download_allowed(downloaded_today[0], downloaded_today=downloaded_today)


def test_reader_matches_repeated_book_after_normalization() -> None:
    reader = make_reader()
    downloaded_today = make_downloaded_ids(_UNVERIFIED_DAILY_DOWNLOAD_LIMIT)

    reader.check_download_allowed(f"  {downloaded_today[0]}  ", downloaded_today=downloaded_today)


@pytest.mark.parametrize(
    "downloaded_count",
    [0, _VERIFIED_DAILY_DOWNLOAD_LIMIT - 1],
)
def test_verified_reader_can_download_within_quota(downloaded_count: int) -> None:
    reader = make_reader(is_verified=True)
    downloaded_today = make_downloaded_ids(downloaded_count)

    reader.check_download_allowed("new-book", downloaded_today=downloaded_today)


def test_verified_reader_is_denied_new_book_at_quota_limit() -> None:
    reader = make_reader(is_verified=True)
    downloaded_today = make_downloaded_ids(_VERIFIED_DAILY_DOWNLOAD_LIMIT)

    with pytest.raises(QuotaExceededError, match=str(_VERIFIED_DAILY_DOWNLOAD_LIMIT)):
        reader.check_download_allowed("new-book", downloaded_today=downloaded_today)


def test_verified_reader_may_repeat_book_at_quota_limit() -> None:
    reader = make_reader(is_verified=True)
    downloaded_today = make_downloaded_ids(_VERIFIED_DAILY_DOWNLOAD_LIMIT)

    reader.check_download_allowed(downloaded_today[-1], downloaded_today=downloaded_today)


@pytest.mark.parametrize("is_verified", [False, True])
def test_suspended_reader_cannot_download_any_book(*, is_verified: bool) -> None:
    reader = make_reader(is_verified=is_verified, is_suspended=True)

    with pytest.raises(ReaderSuspendedError, match="suspended"):
        reader.check_download_allowed("book-1")


@pytest.mark.parametrize("is_verified", [False, True])
def test_suspended_reader_cannot_redownload_already_downloaded_book(*, is_verified: bool) -> None:
    reader = make_reader(is_verified=is_verified, is_suspended=True)

    with pytest.raises(ReaderSuspendedError, match="suspended"):
        reader.check_download_allowed("book-1", downloaded_today=["book-1"])


def test_reader_rejects_empty_book_id_before_quota_check() -> None:
    reader = make_reader()

    with pytest.raises(ValidationError, match="Book id"):
        reader.check_download_allowed("  ")


def test_reader_quota_for_today_rejects_a_bare_string() -> None:
    with pytest.raises(ValidationError, match="not a string"):
        make_reader().quota_for_today("book-1")


def test_check_download_allowed_rejects_a_bare_string_history() -> None:
    with pytest.raises(ValidationError, match="not a string"):
        make_reader().check_download_allowed("book-1", downloaded_today="book-1")
