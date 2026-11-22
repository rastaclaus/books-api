"""Reader entity and the daily anti-bot download quota."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Self

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
        if self.limit <= 0:
            raise ValidationError(f"Daily download limit must be positive, got {self.limit}")

        normalized_ids = frozenset(_normalize_book_id(book_id) for book_id in self.downloaded_book_ids)
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
        """Return a new quota snapshot that includes the downloaded book."""
        normalized_id = _normalize_book_id(book_id)
        return replace(self, downloaded_book_ids=self.downloaded_book_ids | {normalized_id})


@dataclass(frozen=True, slots=True)
class Reader:
    """A person downloading books from the free catalog."""

    id: str
    is_verified: bool = False
    is_suspended: bool = False

    def __post_init__(self) -> None:
        normalized_id = self.id.strip()
        if not normalized_id:
            raise ValidationError("Reader id must not be empty")
        object.__setattr__(self, "id", normalized_id)

    @property
    def daily_download_limit(self) -> int:
        """Return the anti-bot daily download limit for this reader."""
        if self.is_verified:
            return _VERIFIED_DAILY_DOWNLOAD_LIMIT
        return _UNVERIFIED_DAILY_DOWNLOAD_LIMIT

    def quota_for_today(self, downloaded_book_ids: Iterable[str] = ()) -> DailyDownloadQuota:
        """Build today's download quota from the books already downloaded."""
        return DailyDownloadQuota(
            limit=self.daily_download_limit,
            downloaded_book_ids=frozenset(downloaded_book_ids),
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


def _normalize_book_id(book_id: str) -> str:
    normalized_id = book_id.strip()
    if not normalized_id:
        raise ValidationError("Book id must not be empty")
    return normalized_id
