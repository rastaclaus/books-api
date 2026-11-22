"""Entities and the book aggregate of the free e-book catalog."""

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Self

from books_api.domain._checks import (
    ensure_iterable,
    ensure_positive_int,
    ensure_required_text,
    ensure_str,
    has_visible_text,
)
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
        object.__setattr__(self, "id", ensure_required_text(self.id, "Author id"))
        object.__setattr__(self, "full_name", ensure_required_text(self.full_name, "Author full name"))


@dataclass(frozen=True, slots=True)
class BookAsset:
    """A downloadable file of a book in a specific format."""

    format: BookFormat
    size_bytes: int
    checksum: str

    def __post_init__(self) -> None:
        if not isinstance(self.format, BookFormat):
            raise ValidationError("Asset format must be a BookFormat member")

        ensure_positive_int(self.size_bytes, f"Asset size must be a positive integer, got {self.size_bytes!r}")

        normalized_checksum = ensure_str(self.checksum, "Asset checksum must be a string").strip().lower()
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
        self._validate_composition()
        self._normalize_identity()
        self._validate_authors()
        self._validate_assets()
        self._validate_status()

    def add_asset(self, asset: BookAsset, *, replace_existing: bool = False) -> Self:
        """Return a new book with the asset added or its format replaced."""
        if self.status is BookStatus.WITHDRAWN:
            raise InvalidBookStateError("Cannot modify a withdrawn book")
        if not isinstance(asset, BookAsset):
            raise ValidationError("Asset must be a BookAsset instance")
        if not isinstance(replace_existing, bool):
            raise ValidationError("replace_existing flag must be a boolean")

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

        normalized_reason = ensure_required_text(reason, "Withdrawal reason")
        return replace(self, status=BookStatus.WITHDRAWN, withdrawal_reason=normalized_reason)

    @property
    def is_downloadable(self) -> bool:
        """Return whether the book is currently available for download."""
        return self.status is BookStatus.PUBLISHED

    def available_formats(self) -> frozenset[BookFormat]:
        """Return the formats that currently have an asset."""
        return frozenset(asset.format for asset in self.assets)

    def _validate_composition(self) -> None:
        if not isinstance(self.language, LanguageCode):
            raise ValidationError("Book language must be a LanguageCode")
        if not isinstance(self.license, LicenseType):
            raise ValidationError("Book license must be a LicenseType")
        if not isinstance(self.status, BookStatus):
            raise ValidationError("Book status must be a BookStatus")
        if self.isbn is not None and not isinstance(self.isbn, ISBN):
            raise ValidationError("Book ISBN must be an ISBN")
        if self.withdrawal_reason is not None:
            ensure_str(self.withdrawal_reason, "Withdrawal reason must be a string")

    def _normalize_identity(self) -> None:
        object.__setattr__(self, "id", ensure_required_text(self.id, "Book id"))
        object.__setattr__(self, "title", ensure_required_text(self.title, "Book title"))

    def _validate_authors(self) -> None:
        raw_authors = ensure_iterable(self.authors, "Book authors must be an iterable of Author instances")
        authors: list[Author] = []
        for raw_author in raw_authors:
            if not isinstance(raw_author, Author):
                raise ValidationError("Book authors must contain only Author instances")
            authors.append(raw_author)
        object.__setattr__(self, "authors", tuple(authors))

        if not authors:
            raise ValidationError("Book must have at least one author")

        author_ids = {author.id for author in authors}
        if len(author_ids) != len(authors):
            raise ValidationError("Book authors must be unique by id")

    def _validate_assets(self) -> None:
        raw_assets = ensure_iterable(self.assets, "Book assets must be an iterable of BookAsset instances")
        assets: list[BookAsset] = []
        for raw_asset in raw_assets:
            if not isinstance(raw_asset, BookAsset):
                raise ValidationError("Book assets must contain only BookAsset instances")
            assets.append(raw_asset)
        object.__setattr__(self, "assets", tuple(assets))

        formats = {asset.format for asset in assets}
        if len(formats) != len(assets):
            raise DuplicateAssetError("Book cannot contain multiple assets in the same format")

    def _validate_status(self) -> None:
        if self.status is BookStatus.PUBLISHED and not self.assets:
            raise InvalidBookStateError("Published book must have at least one asset")

        if self.status is BookStatus.WITHDRAWN:
            normalized_reason = (self.withdrawal_reason or "").strip()
            if not has_visible_text(normalized_reason):
                raise InvalidBookStateError("Withdrawn book must have a withdrawal reason")
            object.__setattr__(self, "withdrawal_reason", normalized_reason)
        elif self.withdrawal_reason is not None:
            raise ValidationError("Only withdrawn books can have a withdrawal reason")
