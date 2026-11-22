"""Catalog queries and the repository port for browsing books."""

import re
from dataclasses import dataclass
from typing import Protocol, override

from books_api.domain._checks import ensure_required_text, ensure_str, has_visible_text
from books_api.domain.entities import Book
from books_api.domain.errors import ValidationError
from books_api.domain.value_objects import BookFormat, LanguageCode, LicenseType

_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class CatalogQuery:
    """Immutable filter criteria for catalog search.

    ``text`` is matched case-insensitively against the title and every author
    name. Whitespace is collapsed, blank text becomes ``None`` and disables the
    text constraint.
    """

    text: str | None = None
    language: LanguageCode | None = None
    format: BookFormat | None = None
    license: LicenseType | None = None
    only_downloadable: bool = True

    def __post_init__(self) -> None:
        if self.text is not None:
            object.__setattr__(self, "text", _normalize_query_text(self.text))
        if self.language is not None and not isinstance(self.language, LanguageCode):
            raise ValidationError("Catalog query language must be a LanguageCode")
        if self.format is not None and not isinstance(self.format, BookFormat):
            raise ValidationError("Catalog query format must be a BookFormat")
        if self.license is not None and not isinstance(self.license, LicenseType):
            raise ValidationError("Catalog query license must be a LicenseType")
        if not isinstance(self.only_downloadable, bool):
            raise ValidationError("Catalog query only_downloadable flag must be a boolean")


class BookRepository(Protocol):
    """Port for storing and searching books."""

    def add(self, book: Book) -> None:
        """Store a new book, rejecting an id that is already present."""
        ...

    def get(self, book_id: str) -> Book | None:
        """Return the book with the given id, or ``None`` when absent."""
        ...

    def search(self, query: CatalogQuery) -> tuple[Book, ...]:
        """Return books matching the query in insertion order."""
        ...


class InMemoryBookRepository(BookRepository):
    """Pure in-memory reference implementation of the book repository port."""

    __slots__ = ("_books",)

    def __init__(self) -> None:
        self._books: dict[str, Book] = {}

    @override
    def add(self, book: Book) -> None:
        if not isinstance(book, Book):
            raise ValidationError("Catalog can only store Book instances")
        if book.id in self._books:
            raise ValidationError(f"Book with id {book.id!r} already exists in the catalog")
        self._books[book.id] = book

    @override
    def get(self, book_id: str) -> Book | None:
        normalized_id = ensure_required_text(book_id, "Book id")
        return self._books.get(normalized_id)

    @override
    def search(self, query: CatalogQuery) -> tuple[Book, ...]:
        if not isinstance(query, CatalogQuery):
            raise ValidationError("Catalog search requires a CatalogQuery instance")
        return tuple(book for book in self._books.values() if _matches(book, query))


def _normalize_query_text(value: object) -> str | None:
    text = ensure_str(value, "Catalog query text must be a string").strip()
    if not has_visible_text(text):
        return None
    return _WHITESPACE_PATTERN.sub(" ", text)


def _matches(book: Book, query: CatalogQuery) -> bool:
    if query.only_downloadable and not book.is_downloadable:
        return False
    if query.language is not None and book.language != query.language:
        return False
    if query.format is not None and query.format not in book.available_formats():
        return False
    if query.license is not None and book.license is not query.license:
        return False
    if query.text is None:
        return True
    return _matches_text(book, query.text)


def _matches_text(book: Book, text: str) -> bool:
    needle = text.casefold()
    if needle in book.title.casefold():
        return True
    return any(needle in author.full_name.casefold() for author in book.authors)
