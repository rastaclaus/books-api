"""Tests for catalog queries and the in-memory book repository."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from books_api.domain.catalog import CatalogQuery, InMemoryBookRepository
from books_api.domain.entities import Author, Book, BookAsset, BookStatus
from books_api.domain.errors import DomainError, ValidationError
from books_api.domain.value_objects import BookFormat, LanguageCode, LicenseType

_CHECKSUM = "a" * 64

_FRANK = Author(id="author-1", full_name="Frank Herbert")
_ADA = Author(id="author-2", full_name="Ada Lovelace")
_GRACE = Author(id="author-3", full_name="Grace Hopper")


def make_asset(book_format: BookFormat = BookFormat.EPUB) -> BookAsset:
    return BookAsset(format=book_format, size_bytes=1024, checksum=_CHECKSUM)


def make_book(  # noqa: PLR0913 - keyword-only test factory mirrors the Book aggregate
    *,
    book_id: str = "book-1",
    title: str = "Dune",
    language_code: str = "en",
    license_type: LicenseType = LicenseType.CC_BY,
    authors: tuple[Author, ...] = (_FRANK,),
    formats: tuple[BookFormat, ...] = (BookFormat.EPUB,),
    status: BookStatus = BookStatus.PUBLISHED,
    withdrawal_reason: str | None = None,
) -> Book:
    return Book(
        id=book_id,
        title=title,
        language=LanguageCode(language_code),
        license=license_type,
        authors=authors,
        status=status,
        assets=tuple(make_asset(book_format) for book_format in formats),
        withdrawal_reason=withdrawal_reason,
    )


def make_draft_book(*, book_id: str = "draft-1") -> Book:
    return make_book(book_id=book_id, title="Draft Manuscript", status=BookStatus.DRAFT)


def make_withdrawn_book(*, book_id: str = "withdrawn-1") -> Book:
    return make_book(
        book_id=book_id,
        title="Withdrawn Title",
        status=BookStatus.WITHDRAWN,
        withdrawal_reason="Rights dispute",
    )


def make_repository(*books: Book) -> InMemoryBookRepository:
    repository = InMemoryBookRepository()
    for book in books:
        repository.add(book)
    return repository


def test_catalog_query_defaults() -> None:
    query = CatalogQuery()

    assert query.text is None
    assert query.language is None
    assert query.format is None
    assert query.license is None
    assert query.only_downloadable is True


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("Dune", "Dune"),
        ("  Dune  ", "Dune"),
        ("Dune   Messiah", "Dune Messiah"),
        ("\tDune\nMessiah  ", "Dune Messiah"),
        ("", None),
        ("   ", None),
        ("\t\n  ", None),
    ],
)
def test_catalog_query_normalizes_text(*, raw_text: str, expected: str | None) -> None:
    assert CatalogQuery(text=raw_text).text == expected


def _as_object(value: object) -> object:
    return value


@pytest.mark.parametrize(
    "build_query",
    [
        lambda: CatalogQuery(text=cast("str", _as_object(42))),
        lambda: CatalogQuery(language=cast("LanguageCode", _as_object("en"))),
        lambda: CatalogQuery(format=cast("BookFormat", _as_object("epub"))),
        lambda: CatalogQuery(license=cast("LicenseType", _as_object("cc0"))),
        lambda: CatalogQuery(only_downloadable=cast("bool", _as_object("yes"))),
    ],
)
def test_catalog_query_rejects_wrong_field_types(*, build_query: Callable[[], CatalogQuery]) -> None:
    with pytest.raises(ValidationError) as error_info:
        build_query()

    assert isinstance(error_info.value, DomainError)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("text", "changed"),
        ("language", LanguageCode("de")),
        ("format", BookFormat.PDF),
        ("license", LicenseType.CC0),
        ("only_downloadable", False),
    ],
)
def test_catalog_query_is_frozen(*, field_name: str, value: object) -> None:
    query = CatalogQuery()

    with pytest.raises(FrozenInstanceError):
        setattr(query, field_name, value)


def test_add_and_get_roundtrip() -> None:
    book = make_book(book_id="dune")
    repository = InMemoryBookRepository()

    repository.add(book)

    assert repository.get("dune") is book


def test_get_normalizes_the_book_id() -> None:
    book = make_book(book_id="dune")
    repository = make_repository(book)

    assert repository.get("  dune  ") is book


def test_get_returns_none_for_a_missing_book() -> None:
    repository = InMemoryBookRepository()

    assert repository.get("missing") is None


@pytest.mark.parametrize("book_id", ["", "   "])
def test_get_rejects_blank_book_ids(*, book_id: str) -> None:
    repository = InMemoryBookRepository()

    with pytest.raises(ValidationError):
        repository.get(book_id)


def test_duplicate_id_is_rejected() -> None:
    repository = make_repository(make_book(book_id="dune"))

    with pytest.raises(ValidationError, match="already exists"):
        repository.add(make_book(book_id="dune", title="Dune Messiah"))


def test_duplicate_detection_uses_the_normalized_id() -> None:
    repository = make_repository(make_book(book_id="dune"))

    with pytest.raises(ValidationError, match="already exists"):
        repository.add(make_book(book_id="  dune  ", title="Dune Messiah"))


@pytest.mark.parametrize("book", [None, "book", 42])
def test_add_rejects_non_book_values(*, book: object) -> None:
    repository = InMemoryBookRepository()

    with pytest.raises(ValidationError, match="Book instances"):
        repository.add(cast("Book", book))


@pytest.mark.parametrize("query", [None, "dune", 42])
def test_search_rejects_non_query_values(*, query: object) -> None:
    repository = InMemoryBookRepository()

    with pytest.raises(ValidationError, match="CatalogQuery"):
        repository.search(cast("CatalogQuery", query))


def test_search_matches_title_case_insensitively() -> None:
    dune = make_book(title="Dune")
    repository = make_repository(dune)

    assert repository.search(CatalogQuery(text="dune")) == (dune,)
    assert repository.search(CatalogQuery(text="DUNE")) == (dune,)
    assert repository.search(CatalogQuery(text="uNe")) == (dune,)


def test_search_matches_author_name_case_insensitively() -> None:
    dune = make_book(authors=(_FRANK, _ADA, _GRACE))
    repository = make_repository(dune)

    assert repository.search(CatalogQuery(text="herbert")) == (dune,)
    assert repository.search(CatalogQuery(text="FRANK HERBERT")) == (dune,)
    assert repository.search(CatalogQuery(text="ada")) == (dune,)
    assert repository.search(CatalogQuery(text="grace")) == (dune,)


def test_search_matches_collapsed_internal_whitespace() -> None:
    dune = make_book(title="Dune Messiah")
    repository = make_repository(dune)

    assert repository.search(CatalogQuery(text="  dune   messiah ")) == (dune,)


def test_empty_text_adds_no_text_constraint() -> None:
    dune = make_book(book_id="dune", title="Dune")
    emma = make_book(book_id="emma", title="Emma", authors=(_ADA,))
    repository = make_repository(dune, emma)

    assert repository.search(CatalogQuery(text="   ")) == (dune, emma)


def test_search_filters_by_language() -> None:
    english = make_book(book_id="en-book", language_code="en")
    german = make_book(book_id="de-book", language_code="de")
    repository = make_repository(english, german)

    assert repository.search(CatalogQuery(language=LanguageCode("en"))) == (english,)
    assert repository.search(CatalogQuery(language=LanguageCode("de"))) == (german,)


def test_search_filters_by_format_membership() -> None:
    epub_only = make_book(book_id="epub-only", formats=(BookFormat.EPUB,))
    both = make_book(book_id="both", formats=(BookFormat.EPUB, BookFormat.PDF))
    repository = make_repository(epub_only, both)

    assert repository.search(CatalogQuery(format=BookFormat.PDF)) == (both,)
    assert repository.search(CatalogQuery(format=BookFormat.EPUB)) == (epub_only, both)


def test_search_filters_by_license() -> None:
    cc0_book = make_book(book_id="cc0", license_type=LicenseType.CC0)
    by_book = make_book(book_id="by", license_type=LicenseType.CC_BY)
    repository = make_repository(cc0_book, by_book)

    assert repository.search(CatalogQuery(license=LicenseType.CC0)) == (cc0_book,)
    assert repository.search(CatalogQuery(license=LicenseType.CC_BY)) == (by_book,)


def test_search_excludes_non_downloadable_books_by_default() -> None:
    published = make_book(book_id="published")
    draft = make_draft_book()
    withdrawn = make_withdrawn_book()
    repository = make_repository(published, draft, withdrawn)

    assert repository.search(CatalogQuery()) == (published,)


def test_search_can_include_non_downloadable_books() -> None:
    published = make_book(book_id="published")
    draft = make_draft_book()
    withdrawn = make_withdrawn_book()
    repository = make_repository(published, draft, withdrawn)

    assert repository.search(CatalogQuery(only_downloadable=False)) == (published, draft, withdrawn)


def test_search_combines_all_filters() -> None:
    match = make_book(
        book_id="match",
        title="Dune",
        language_code="en",
        license_type=LicenseType.CC0,
        authors=(_FRANK,),
        formats=(BookFormat.EPUB, BookFormat.PDF),
    )
    wrong_language = make_book(
        book_id="wrong-language",
        title="Dune",
        language_code="de",
        license_type=LicenseType.CC0,
        authors=(_FRANK,),
        formats=(BookFormat.EPUB,),
    )
    repository = make_repository(match, wrong_language)

    query = CatalogQuery(
        text="herbert",
        language=LanguageCode("en"),
        format=BookFormat.PDF,
        license=LicenseType.CC0,
        only_downloadable=True,
    )

    assert repository.search(query) == (match,)


def test_search_returns_an_empty_tuple_when_nothing_matches() -> None:
    repository = make_repository(make_book(title="Dune"))

    assert repository.search(CatalogQuery(text="emma")) == ()


def test_search_preserves_insertion_order() -> None:
    first = make_book(book_id="first", title="Dune")
    second = make_book(book_id="second", title="Dune Messiah")
    third = make_book(book_id="third", title="Children of Dune")
    repository = make_repository(first, second, third)

    assert repository.search(CatalogQuery(text="dune")) == (first, second, third)
