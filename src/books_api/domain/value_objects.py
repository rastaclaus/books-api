"""Value objects of the free e-book catalog domain.

Each value object is immutable and guarantees its own invariants: an instance
cannot exist in an invalid state. Invalid input raises a subclass of
:class:`books_api.domain.errors.DomainError`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from books_api.domain.errors import LicenseViolationError, ValidationError

__all__ = ["ISBN", "BookFormat", "LanguageCode", "LicenseType"]

# --- Language codes -------------------------------------------------------

LANGUAGE_CODE_PATTERN = re.compile(r"[a-z]{2}")

# --- ISBN -----------------------------------------------------------------

ISBN10_LENGTH = 10
ISBN13_LENGTH = 13
ISBN_SEPARATORS = ("-", " ")
ISBN10_CHECK_CHAR = "X"
ISBN10_CHECK_VALUE = 10
ISBN10_WEIGHTS = (10, 9, 8, 7, 6, 5, 4, 3, 2, 1)
ISBN13_WEIGHTS = (1, 3)
ISBN10_MODULUS = 11
ISBN13_MODULUS = 10


class BookFormat(StrEnum):
    """Supported e-book file formats."""

    EPUB = "epub"
    PDF = "pdf"
    MOBI = "mobi"


@dataclass(frozen=True, slots=True)
class LanguageCode:
    """Two-letter language code as defined by ISO 639-1."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if LANGUAGE_CODE_PATTERN.fullmatch(normalized) is None:
            raise ValidationError(f"Invalid language code: {self.value!r}")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True, slots=True)
class ISBN:
    """ISBN-10 or ISBN-13 identifier stored without separators."""

    value: str

    def __post_init__(self) -> None:
        normalized = _strip_isbn_separators(self.value).upper()
        if not _is_isbn_valid(normalized):
            raise ValidationError(f"Invalid ISBN: {self.value!r}")
        object.__setattr__(self, "value", normalized)


class LicenseType(StrEnum):
    """Free-distribution license of an e-book."""

    PUBLIC_DOMAIN = "public_domain"
    CC0 = "cc0"
    CC_BY = "cc_by"
    CC_BY_SA = "cc_by_sa"

    @classmethod
    def from_string(cls, value: str) -> LicenseType:
        """Build a license from a string, rejecting unfree licenses."""
        try:
            return cls(value.strip().lower())
        except ValueError as error:
            raise LicenseViolationError(f"Unfree or unknown license: {value!r}") from error

    @property
    def requires_attribution(self) -> bool:
        """Whether the license requires crediting the author."""
        return self in (LicenseType.CC_BY, LicenseType.CC_BY_SA)

    @property
    def is_share_alike(self) -> bool:
        """Whether derivative works must keep the same license."""
        return self is LicenseType.CC_BY_SA


def _strip_isbn_separators(raw: str) -> str:
    normalized = raw
    for separator in ISBN_SEPARATORS:
        normalized = normalized.replace(separator, "")
    return normalized


def _is_ascii_digit(char: str) -> bool:
    return char.isascii() and char.isdigit()


def _is_isbn_valid(value: str) -> bool:
    if len(value) == ISBN10_LENGTH:
        return _is_isbn10_valid(value)
    if len(value) == ISBN13_LENGTH:
        return _is_isbn13_valid(value)
    return False


def _is_isbn10_valid(value: str) -> bool:
    total = 0
    for index, char in enumerate(value):
        if char == ISBN10_CHECK_CHAR:
            if index != ISBN10_LENGTH - 1:
                return False
            digit = ISBN10_CHECK_VALUE
        elif _is_ascii_digit(char):
            digit = int(char)
        else:
            return False
        total += digit * ISBN10_WEIGHTS[index]
    return total % ISBN10_MODULUS == 0


def _is_isbn13_valid(value: str) -> bool:
    if not all(_is_ascii_digit(char) for char in value):
        return False
    total = 0
    for index, char in enumerate(value):
        total += int(char) * ISBN13_WEIGHTS[index % len(ISBN13_WEIGHTS)]
    return total % ISBN13_MODULUS == 0
