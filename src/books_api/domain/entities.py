"""Entities and the book aggregate of the free e-book catalog."""

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Self

from books_api.domain.errors import (
    DuplicateAssetError,
    InvalidBookStateError,
    ValidationError,
)
from books_api.domain.value_objects import ISBN, BookFormat, LanguageCode, LicenseType

_SHA256_HEX_LENGTH = 64
_SHA256_PATTERN = re.compile(rf"[0-9a-f]{{{_SHA256_HEX_LENGTH}}}")


class BookStatus(StrEnum):
    """Lifecycle status of a book."""

    DRAFT = "draft"
    PUBLISHED = "published"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True, slots=True)
class Author:
    """Author credited for a book."""

    id: str
    full_name: str

    def __post_init__(self) -> None:
        normalized_id = self.id.strip()
        if not normalized_id:
            raise ValidationError("Author id must not be empty")
        object.__setattr__(self, "id", normalized_id)

        normalized_name = self.full_name.strip()
        if not normalized_name:
            raise ValidationError("Author full name must not be empty")
        object.__setattr__(self, "full_name", normalized_name)


@dataclass(frozen=True, slots=True)
class BookAsset:
    """A downloadable file of a book in a specific format."""

    format: BookFormat
    size_bytes: int
    checksum: str

    def __post_init__(self) -> None:
        if self.size_bytes <= 0:
            raise ValidationError(f"Asset size must be positive, got {self.size_bytes}")

        normalized_checksum = self.checksum.strip().lower()
        if _SHA256_PATTERN.fullmatch(normalized_checksum) is None:
            raise ValidationError("Asset checksum must be a 64-character SHA-256 hex digest")
        object.__setattr__(self, "checksum", normalized_checksum)


@dataclass(frozen=True, slots=True, kw_only=True)
class Book:
    """Aggregate root for a book and its downloadable assets."""

    id: str
    title: str
    language: LanguageCode
    license: LicenseType
    authors: tuple[Author, ...]
    isbn: ISBN | None = None
    status: BookStatus = BookStatus.DRAFT
    assets: tuple[BookAsset, ...] = ()
    withdrawal_reason: str | None = None

    def __post_init__(self) -> None:
        self._normalize_identity()
        self._validate_authors()
        self._validate_assets()
        self._validate_status()

    def add_asset(self, asset: BookAsset, *, replace_existing: bool = False) -> Self:
        """Return a new book with the asset added or its format replaced."""
        if self.status is BookStatus.WITHDRAWN:
            raise InvalidBookStateError("Cannot modify a withdrawn book")

        has_format = any(current.format is asset.format for current in self.assets)
        if has_format and not replace_existing:
            raise DuplicateAssetError(f"Book already has an asset in {asset.format.value} format")

        if has_format:
            updated_assets = tuple(asset if current.format is asset.format else current for current in self.assets)
        else:
            updated_assets = (*self.assets, asset)
        return replace(self, assets=updated_assets)

    def publish(self) -> Self:
        """Return a published copy of a draft book that has at least one asset."""
        if self.status is not BookStatus.DRAFT:
            raise InvalidBookStateError(f"Cannot publish a book in {self.status.value} status")
        if not self.assets:
            raise InvalidBookStateError("Cannot publish a book without assets")
        return replace(self, status=BookStatus.PUBLISHED)

    def withdraw(self, reason: str) -> Self:
        """Return a withdrawn copy of a published book."""
        if self.status is not BookStatus.PUBLISHED:
            raise InvalidBookStateError(f"Cannot withdraw a book in {self.status.value} status")

        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValidationError("Withdrawal reason must not be empty")
        return replace(self, status=BookStatus.WITHDRAWN, withdrawal_reason=normalized_reason)

    @property
    def is_downloadable(self) -> bool:
        """Return whether the book is currently available for download."""
        return self.status is BookStatus.PUBLISHED

    def available_formats(self) -> frozenset[BookFormat]:
        """Return the formats that currently have an asset."""
        return frozenset(asset.format for asset in self.assets)

    def _normalize_identity(self) -> None:
        normalized_id = self.id.strip()
        if not normalized_id:
            raise ValidationError("Book id must not be empty")
        object.__setattr__(self, "id", normalized_id)

        normalized_title = self.title.strip()
        if not normalized_title:
            raise ValidationError("Book title must not be empty")
        object.__setattr__(self, "title", normalized_title)

    def _validate_authors(self) -> None:
        authors = tuple(self.authors)
        object.__setattr__(self, "authors", authors)
        if not authors:
            raise ValidationError("Book must have at least one author")

        author_ids = {author.id for author in authors}
        if len(author_ids) != len(authors):
            raise ValidationError("Book authors must be unique by id")

    def _validate_assets(self) -> None:
        assets = tuple(self.assets)
        object.__setattr__(self, "assets", assets)
        formats = {asset.format for asset in assets}
        if len(formats) != len(assets):
            raise DuplicateAssetError("Book cannot contain multiple assets in the same format")

    def _validate_status(self) -> None:
        if self.status is BookStatus.PUBLISHED and not self.assets:
            raise InvalidBookStateError("Published book must have at least one asset")

        if self.status is BookStatus.WITHDRAWN:
            normalized_reason = (self.withdrawal_reason or "").strip()
            if not normalized_reason:
                raise InvalidBookStateError("Withdrawn book must have a withdrawal reason")
            object.__setattr__(self, "withdrawal_reason", normalized_reason)
        elif self.withdrawal_reason is not None:
            raise ValidationError("Only withdrawn books can have a withdrawal reason")
