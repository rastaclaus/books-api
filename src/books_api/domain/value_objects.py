"""Immutable value objects for the free e-book catalog."""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Self, override

from books_api.domain.errors import LicenseViolationError, ValidationError

_LANGUAGE_CODE_LENGTH = 2

_ISBN_10_LENGTH = 10
_ISBN_13_LENGTH = 13
_ISBN_10_CHECK_MODULUS = 11
_ISBN_13_CHECK_MODULUS = 10
_ISBN_13_ALTERNATING_WEIGHT = 3
_ISBN_X_VALUE = 10

_ISBN_SEPARATORS = re.compile(r"[-\s]")
_LICENSE_SEPARATORS = re.compile(r"[^a-z0-9]+")


class BookFormat(StrEnum):
    """Formats allowed for free distribution."""

    EPUB = "epub"
    PDF = "pdf"
    MOBI = "mobi"
    FB2 = "fb2"


@dataclass(frozen=True, slots=True)
class LanguageCode:
    """Two-letter ISO 639-1 language code."""

    value: str

    def __post_init__(self) -> None:
        canonical = self.value.strip().lower()
        is_two_latin_letters = len(canonical) == _LANGUAGE_CODE_LENGTH and canonical.isascii() and canonical.isalpha()
        if not is_two_latin_letters:
            raise ValidationError(f"Language code must be exactly two Latin letters: {self.value!r}")
        object.__setattr__(self, "value", canonical)


@dataclass(frozen=True, slots=True)
class ISBN:
    """Canonical ISBN-10 or ISBN-13 without separators."""

    value: str

    def __post_init__(self) -> None:
        canonical = _ISBN_SEPARATORS.sub("", self.value).upper()
        _validate_isbn(canonical)
        object.__setattr__(self, "value", canonical)


class LicenseType(StrEnum):
    """Licenses that permit legal free distribution."""

    PUBLIC_DOMAIN = "public-domain"
    CC0 = "cc0"
    CC_BY = "cc-by"
    CC_BY_SA = "cc-by-sa"

    @property
    def requires_attribution(self) -> bool:
        """Return whether the license requires crediting the author."""
        return self in {LicenseType.CC_BY, LicenseType.CC_BY_SA}

    @property
    def is_share_alike(self) -> bool:
        """Return whether derivative works must keep the same license."""
        return self is LicenseType.CC_BY_SA

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Parse a license identifier, rejecting non-free licenses."""
        return cls(raw)

    @classmethod
    @override
    def _missing_(cls, value: object) -> Self:
        if not isinstance(value, str):
            raise LicenseViolationError(f"License must be a string, got {type(value).__name__}")
        normalized = _normalize_license(value)
        for member in cls:
            if member.value == normalized:
                return member
        raise LicenseViolationError(f"License {value!r} does not allow free distribution")


def _validate_isbn(canonical: str) -> None:
    if len(canonical) == _ISBN_10_LENGTH:
        _validate_isbn_10(canonical)
    elif len(canonical) == _ISBN_13_LENGTH:
        _validate_isbn_13(canonical)
    else:
        raise ValidationError(f"ISBN must contain 10 or 13 characters, got {len(canonical)}")


def _validate_isbn_10(canonical: str) -> None:
    body = canonical[:-1]
    if not (body.isascii() and body.isdigit()):
        raise ValidationError(f"ISBN-10 must contain nine digits followed by a check digit: {canonical!r}")
    weighted_sum = sum((_ISBN_10_LENGTH - index) * int(digit) for index, digit in enumerate(body))
    weighted_sum += _parse_isbn_10_check_digit(canonical[-1])
    if weighted_sum % _ISBN_10_CHECK_MODULUS != 0:
        raise ValidationError(f"ISBN-10 check digit is invalid: {canonical!r}")


def _parse_isbn_10_check_digit(digit: str) -> int:
    if digit == "X":
        return _ISBN_X_VALUE
    if digit.isascii() and digit.isdigit():
        return int(digit)
    raise ValidationError(f"ISBN-10 check digit must be a digit or 'X': {digit!r}")


def _validate_isbn_13(canonical: str) -> None:
    if not (canonical.isascii() and canonical.isdigit()):
        raise ValidationError(f"ISBN-13 must contain only digits: {canonical!r}")
    weighted_sum = sum(
        int(digit) * (_ISBN_13_ALTERNATING_WEIGHT if index % 2 else 1) for index, digit in enumerate(canonical)
    )
    if weighted_sum % _ISBN_13_CHECK_MODULUS != 0:
        raise ValidationError(f"ISBN-13 check digit is invalid: {canonical!r}")


def _normalize_license(raw: str) -> str:
    return _LICENSE_SEPARATORS.sub("-", raw.strip().lower()).strip("-")
