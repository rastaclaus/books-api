"""Reader entity and the daily anti-bot download quota."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Self

from books_api.domain._checks import ensure_iterable, ensure_positive_int, ensure_required_text
from books_api.domain.errors import (
    QuotaExceededError,
    ReaderSuspendedError,
    ValidationError,
)

_UNVERIFIED_DAILY_DOWNLOAD_LIMIT = 3
_VERIFIED_DAILY_DOWNLOAD_LIMIT = 25


@dataclass(frozen=True, slots=True)
class DailyDownloadQuota:
    """Snapshot of a reader's daily download allowance and consumed books."""

    limit: int
    downloaded_book_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        ensure_positive_int(self.limit, f"Daily download limit must be a positive integer, got {self.limit!r}")

        raw_ids = ensure_iterable(
            self.downloaded_book_ids,
            "Downloaded book ids must be an iterable of book ids, not a string",
        )
        normalized_ids = frozenset(_normalize_book_id(book_id) for book_id in raw_ids)
        object.__setattr__(self, "downloaded_book_ids", normalized_ids)

    @property
    def used(self) -> int:
        """Return how many distinct books were downloaded today."""
        return len(self.downloaded_book_ids)

    @property
    def remaining(self) -> int:
        """Return how many new books may still be downloaded today."""
        return max(self.limit - self.used, 0)

    def allows(self, book_id: str) -> bool:
        """Return whether downloading the book stays within the quota."""
        normalized_id = _normalize_book_id(book_id)
        return normalized_id in self.downloaded_book_ids or self.used < self.limit

    def register(self, book_id: str) -> Self:
        """Return a new quota snapshot that includes the downloaded book.

        Registering a new book beyond the limit is rejected, while re-registering
        an already downloaded book stays allowed.
        """
        normalized_id = _normalize_book_id(book_id)
        if not self.allows(normalized_id):
            raise QuotaExceededError(f"Daily download limit of {self.limit} books has been reached")
        return replace(self, downloaded_book_ids=self.downloaded_book_ids | {normalized_id})


@dataclass(frozen=True, slots=True)
class Reader:
    """A person downloading books from the free catalog."""

    id: str
    is_verified: bool = False
    is_suspended: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", ensure_required_text(self.id, "Reader id"))

        if not isinstance(self.is_verified, bool):
            raise ValidationError("Reader is_verified flag must be a boolean")
        if not isinstance(self.is_suspended, bool):
            raise ValidationError("Reader is_suspended flag must be a boolean")

    @property
    def daily_download_limit(self) -> int:
        """Return the anti-bot daily download limit for this reader."""
        if self.is_verified:
            return _VERIFIED_DAILY_DOWNLOAD_LIMIT
        return _UNVERIFIED_DAILY_DOWNLOAD_LIMIT

    def quota_for_today(self, downloaded_book_ids: Iterable[str] = ()) -> DailyDownloadQuota:
        """Build today's download quota from the books already downloaded."""
        raw_ids = ensure_iterable(
            downloaded_book_ids,
            "Downloaded book ids must be an iterable of book ids, not a string",
        )
        return DailyDownloadQuota(
            limit=self.daily_download_limit,
            downloaded_book_ids=frozenset(_normalize_book_id(book_id) for book_id in raw_ids),
        )

    def check_download_allowed(
        self,
        book_id: str,
        *,
        downloaded_today: Iterable[str] = (),
    ) -> None:
        """Raise when the reader may not download the book today.

        A suspended reader is never allowed to download. Re-downloading a book
        that was already downloaded today does not consume the quota again.
        """
        normalized_id = _normalize_book_id(book_id)

        if self.is_suspended:
            raise ReaderSuspendedError(f"Reader {self.id!r} is suspended and cannot download books")

        if not self.quota_for_today(downloaded_today).allows(normalized_id):
            raise QuotaExceededError(
                f"Reader {self.id!r} reached the daily download limit of {self.daily_download_limit} books"
            )


def _normalize_book_id(book_id: object) -> str:
    return ensure_required_text(book_id, "Book id")
