from __future__ import annotations

import pytest

from books_api.domain import (
    ISBN,
    BookFormat,
    LanguageCode,
    LicenseType,
    LicenseViolationError,
    ValidationError,
)

# --- BookFormat -----------------------------------------------------------


def test_book_format_members() -> None:
    assert set(BookFormat) == {BookFormat.EPUB, BookFormat.PDF, BookFormat.MOBI}


def test_book_format_is_str_enum() -> None:
    assert BookFormat.EPUB == "epub"
    assert BookFormat.MOBI.upper() == "MOBI"


# --- LanguageCode ---------------------------------------------------------


def test_language_code_happy_path() -> None:
    assert LanguageCode("en").value == "en"


def test_language_code_normalizes_case_and_whitespace() -> None:
    assert LanguageCode("  RU ").value == "ru"
    assert LanguageCode("De").value == "de"


def test_language_code_normalization_is_idempotent() -> None:
    once = LanguageCode("PT").value

    assert LanguageCode(once).value == once


@pytest.mark.parametrize("raw", ["", "e", "eng", "e1", "12", "ru-RU", "ёж"])
def test_language_code_rejects_invalid_format(raw: str) -> None:
    with pytest.raises(ValidationError):
        LanguageCode(raw)


# --- ISBN -----------------------------------------------------------------


def test_isbn_happy_path_isbn10() -> None:
    assert ISBN("0306406152").value == "0306406152"


def test_isbn_happy_path_isbn13() -> None:
    assert ISBN("9780306406157").value == "9780306406157"


def test_isbn_strips_separators() -> None:
    assert ISBN("0-306-40615-2").value == "0306406152"
    assert ISBN("978 0 306 40615 7").value == "9780306406157"


def test_isbn_accepts_x_check_digit() -> None:
    assert ISBN("080442957X").value == "080442957X"
    assert ISBN("0-8044-2957-x").value == "080442957X"


def test_isbn_normalization_is_idempotent() -> None:
    once = ISBN("978-0-306-40615-7").value

    assert ISBN(once).value == once


@pytest.mark.parametrize(
    "raw",
    [
        "0306406153",
        "9780306406158",
        "0804429570",
    ],
)
def test_isbn_rejects_invalid_check_digit(raw: str) -> None:
    with pytest.raises(ValidationError):
        ISBN(raw)


@pytest.mark.parametrize(
    "raw",
    ["", "123", "03064061527", "97803064061571", "97803064061X7", "abcdefghij"],
)
def test_isbn_rejects_invalid_shape(raw: str) -> None:
    with pytest.raises(ValidationError):
        ISBN(raw)


# --- LicenseType ----------------------------------------------------------


@pytest.mark.parametrize(
    ("license_type", "requires_attribution", "is_share_alike"),
    [
        (LicenseType.PUBLIC_DOMAIN, False, False),
        (LicenseType.CC0, False, False),
        (LicenseType.CC_BY, True, False),
        (LicenseType.CC_BY_SA, True, True),
    ],
)
def test_license_flags(
    license_type: LicenseType,
    *,
    requires_attribution: bool,
    is_share_alike: bool,
) -> None:
    assert license_type.requires_attribution is requires_attribution
    assert license_type.is_share_alike is is_share_alike


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("public_domain", LicenseType.PUBLIC_DOMAIN),
        ("cc0", LicenseType.CC0),
        ("CC_BY", LicenseType.CC_BY),
        (" cc_by_sa ", LicenseType.CC_BY_SA),
    ],
)
def test_license_from_string_accepts_free_licenses(raw: str, expected: LicenseType) -> None:
    assert LicenseType.from_string(raw) is expected


@pytest.mark.parametrize(
    "raw",
    ["proprietary", "commercial", "all rights reserved", ""],
)
def test_license_from_string_rejects_unfree_licenses(raw: str) -> None:
    with pytest.raises(LicenseViolationError):
        LicenseType.from_string(raw)
