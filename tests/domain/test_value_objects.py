"""Tests for the catalog value objects."""

import dataclasses

import pytest

from books_api.domain import (
    ISBN,
    BookFormat,
    DomainError,
    LanguageCode,
    LicenseType,
    LicenseViolationError,
    ValidationError,
)


def test_book_format_exposes_exactly_free_distribution_formats() -> None:
    assert {member.value for member in BookFormat} == {"epub", "pdf", "mobi", "fb2"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("epub", BookFormat.EPUB),
        ("pdf", BookFormat.PDF),
        ("mobi", BookFormat.MOBI),
        ("fb2", BookFormat.FB2),
    ],
)
def test_book_format_parses_supported_values(raw: str, expected: BookFormat) -> None:
    assert BookFormat(raw) is expected


@pytest.mark.parametrize("raw", ["txt", "EPUB", "", "djvu"])
def test_book_format_rejects_unsupported_values(raw: str) -> None:
    with pytest.raises(ValueError, match="is not a valid BookFormat"):
        BookFormat(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ru", "ru"),
        ("en", "en"),
        ("EN", "en"),
        ("  Ru  ", "ru"),
        ("DE", "de"),
    ],
)
def test_language_code_normalizes_case_and_whitespace(raw: str, expected: str) -> None:
    assert LanguageCode(raw).value == expected


@pytest.mark.parametrize(
    "raw",
    ["", " ", "e", "eng", "e1", "12", "ру", "e_", "e n", "EN-US"],
)
def test_language_code_rejects_non_two_latin_letters(raw: str) -> None:
    with pytest.raises(ValidationError, match="two Latin letters"):
        LanguageCode(raw)


def test_language_code_validation_error_is_a_domain_error() -> None:
    with pytest.raises(ValidationError) as error_info:
        LanguageCode("ру")

    assert isinstance(error_info.value, DomainError)


def test_language_code_equality_uses_canonical_value() -> None:
    assert LanguageCode("RU") == LanguageCode("ru")
    assert hash(LanguageCode("RU")) == hash(LanguageCode("ru"))


def test_language_code_is_a_frozen_slots_value_object() -> None:
    code = LanguageCode("ru")

    assert [field.name for field in dataclasses.fields(LanguageCode)] == ["value"]
    assert not hasattr(code, "__dict__")
    assert dataclasses.replace(code, value="EN") == LanguageCode("en")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0306406152", "0306406152"),
        ("0-306-40615-2", "0306406152"),
        (" 0 306 40615 2 ", "0306406152"),
        ("080442957X", "080442957X"),
        ("0-8044-2957-x", "080442957X"),
        ("9780306406157", "9780306406157"),
        ("978-0-306-40615-7", "9780306406157"),
        (" 978 0 306 40615 7 ", "9780306406157"),
    ],
)
def test_isbn_accepts_and_canonicalizes_valid_values(raw: str, expected: str) -> None:
    assert ISBN(raw).value == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "123456789",
        "12345678901",
        "0306406153",
        "9780306406158",
        "03064061X2",
        "030640615A",
        "978030640615X",
        "not-an-isbn",
        "0306406152 extra",
    ],
)
def test_isbn_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValidationError):
        ISBN(raw)


def test_isbn_rejects_wrong_length_with_message() -> None:
    with pytest.raises(ValidationError, match="10 or 13"):
        ISBN("123")


def test_isbn_equality_uses_canonical_value() -> None:
    assert ISBN("0-306-40615-2") == ISBN("0306406152")
    assert hash(ISBN("978-0-306-40615-7")) == hash(ISBN("9780306406157"))


def test_license_type_exposes_only_free_licenses() -> None:
    assert {member.value for member in LicenseType} == {
        "public-domain",
        "cc0",
        "cc-by",
        "cc-by-sa",
    }


@pytest.mark.parametrize(
    ("license_", "requires_attribution", "is_share_alike"),
    [
        (LicenseType.PUBLIC_DOMAIN, False, False),
        (LicenseType.CC0, False, False),
        (LicenseType.CC_BY, True, False),
        (LicenseType.CC_BY_SA, True, True),
    ],
)
def test_license_type_flags(
    license_: LicenseType,
    *,
    requires_attribution: bool,
    is_share_alike: bool,
) -> None:
    assert license_.requires_attribution is requires_attribution
    assert license_.is_share_alike is is_share_alike


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("public-domain", LicenseType.PUBLIC_DOMAIN),
        ("PUBLIC_DOMAIN", LicenseType.PUBLIC_DOMAIN),
        ("  Public Domain  ", LicenseType.PUBLIC_DOMAIN),
        ("cc0", LicenseType.CC0),
        ("CC0", LicenseType.CC0),
        ("cc-by", LicenseType.CC_BY),
        ("CC BY", LicenseType.CC_BY),
        ("CC_BY_SA", LicenseType.CC_BY_SA),
        ("cc-by-sa", LicenseType.CC_BY_SA),
        (" CC BY-SA ", LicenseType.CC_BY_SA),
    ],
)
def test_license_type_parses_free_licenses(raw: str, expected: LicenseType) -> None:
    assert LicenseType.parse(raw) is expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "proprietary",
        "all-rights-reserved",
        "copyright",
        "cc-by-nc",
        "cc-by-nd",
        "cc-by-nc-sa",
    ],
)
def test_license_type_parse_rejects_non_free_licenses(raw: str) -> None:
    with pytest.raises(LicenseViolationError, match="does not allow free distribution"):
        LicenseType.parse(raw)


@pytest.mark.parametrize("raw", ["proprietary", "cc-by-nc"])
def test_license_type_constructor_rejects_non_free_licenses(raw: str) -> None:
    with pytest.raises(LicenseViolationError):
        LicenseType(raw)
