"""Tests for license notices and anthology license resolution."""

from collections.abc import Sequence
from typing import cast

import pytest

from books_api.domain import (
    Author,
    Book,
    DomainError,
    LanguageCode,
    LicenseType,
    LicenseViolationError,
    ValidationError,
)
from books_api.domain.license_policy import (
    SPDX_IDENTIFIERS,
    build_license_notice,
    resolve_anthology_license,
)

_ADA = Author(id="author-1", full_name="Ada Lovelace")
_GRACE = Author(id="author-2", full_name="Grace Hopper")

_EXPECTED_SPDX = {
    LicenseType.PUBLIC_DOMAIN: "CC-PDDC",
    LicenseType.CC0: "CC0-1.0",
    LicenseType.CC_BY: "CC-BY-4.0",
    LicenseType.CC_BY_SA: "CC-BY-SA-4.0",
}


def make_book(
    *,
    book_id: str = "book-1",
    license_type: LicenseType = LicenseType.CC0,
    authors: tuple[Author, ...] = (_ADA,),
) -> Book:
    return Book(
        id=book_id,
        title="Structure and Interpretation",
        language=LanguageCode("en"),
        license=license_type,
        authors=authors,
    )


def test_spdx_identifiers_match_the_license_catalog() -> None:
    assert dict(SPDX_IDENTIFIERS) == _EXPECTED_SPDX


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
def test_build_license_notice_uses_the_exact_catalog_template(
    *,
    license_type: LicenseType,
    expected: str,
) -> None:
    assert build_license_notice(make_book(license_type=license_type)) == expected


def test_build_license_notice_lists_every_author_for_attribution_licenses() -> None:
    book = make_book(license_type=LicenseType.CC_BY_SA, authors=(_ADA, _GRACE))

    notice = build_license_notice(book)

    assert notice == ("Licensed under CC BY-SA 4.0. Attribution to Ada Lovelace, Grace Hopper and ShareAlike required.")


@pytest.mark.parametrize("license_type", [LicenseType.PUBLIC_DOMAIN, LicenseType.CC0])
def test_build_license_notice_ignores_authors_without_attribution(*, license_type: LicenseType) -> None:
    book = make_book(license_type=license_type, authors=(_ADA, _GRACE))

    notice = build_license_notice(book)

    assert "Ada Lovelace" not in notice
    assert "Grace Hopper" not in notice


@pytest.mark.parametrize("book", [None, "book", 42, object()])
def test_build_license_notice_rejects_non_book_values(*, book: object) -> None:
    with pytest.raises(ValidationError, match="Book instance"):
        build_license_notice(cast("Book", book))


@pytest.mark.parametrize(
    ("license_types", "expected"),
    [
        ((LicenseType.PUBLIC_DOMAIN,), LicenseType.PUBLIC_DOMAIN),
        ((LicenseType.CC0,), LicenseType.CC0),
        ((LicenseType.CC_BY,), LicenseType.CC_BY),
        ((LicenseType.CC_BY_SA,), LicenseType.CC_BY_SA),
        ((LicenseType.PUBLIC_DOMAIN, LicenseType.CC0), LicenseType.CC0),
        ((LicenseType.CC0, LicenseType.PUBLIC_DOMAIN), LicenseType.CC0),
        ((LicenseType.PUBLIC_DOMAIN, LicenseType.CC_BY), LicenseType.CC_BY),
        ((LicenseType.CC0, LicenseType.CC_BY), LicenseType.CC_BY),
        ((LicenseType.CC_BY, LicenseType.CC_BY_SA), LicenseType.CC_BY_SA),
        ((LicenseType.CC_BY_SA, LicenseType.PUBLIC_DOMAIN), LicenseType.CC_BY_SA),
        (
            (LicenseType.PUBLIC_DOMAIN, LicenseType.CC0, LicenseType.CC_BY, LicenseType.CC_BY_SA),
            LicenseType.CC_BY_SA,
        ),
    ],
)
def test_resolve_anthology_license_follows_share_alike_precedence(
    *,
    license_types: tuple[LicenseType, ...],
    expected: LicenseType,
) -> None:
    books = [make_book(book_id=f"book-{index}", license_type=item) for index, item in enumerate(license_types)]

    assert resolve_anthology_license(books) is expected


def test_resolve_anthology_license_accepts_a_tuple() -> None:
    books = (make_book(license_type=LicenseType.CC_BY), make_book(book_id="book-2"))

    assert resolve_anthology_license(books) is LicenseType.CC_BY


@pytest.mark.parametrize("books", [[], ()])
def test_resolve_anthology_license_rejects_an_empty_collection(*, books: Sequence[Book]) -> None:
    with pytest.raises(LicenseViolationError, match="at least one book") as error_info:
        resolve_anthology_license(books)

    assert isinstance(error_info.value, DomainError)


@pytest.mark.parametrize("books", [None, "book", b"book", 42, iter(())])
def test_resolve_anthology_license_rejects_non_sequences(*, books: object) -> None:
    with pytest.raises(ValidationError, match="sequence of Book instances"):
        resolve_anthology_license(cast("Sequence[Book]", books))


@pytest.mark.parametrize(
    "books",
    [
        [None],
        [make_book(), "book"],
        [make_book(), 42],
        [object()],
    ],
)
def test_resolve_anthology_license_rejects_non_book_items(*, books: list[object]) -> None:
    with pytest.raises(ValidationError, match="only Book instances"):
        resolve_anthology_license(cast("Sequence[Book]", books))
