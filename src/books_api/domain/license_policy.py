"""License policy for e-book notices and anthology licensing.

The catalog metadata mirrors the ``books-licenses`` MCP server: SPDX
identifiers and mandatory notice templates are kept verbatim so generated
notices stay legally exact.
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Final

from books_api.domain.entities import Book
from books_api.domain.errors import LicenseViolationError, ValidationError
from books_api.domain.value_objects import LicenseType

_AUTHORS_PLACEHOLDER = "{authors}"

SPDX_IDENTIFIERS: Final[Mapping[LicenseType, str]] = MappingProxyType(
    {
        LicenseType.PUBLIC_DOMAIN: "CC-PDDC",
        LicenseType.CC0: "CC0-1.0",
        LicenseType.CC_BY: "CC-BY-4.0",
        LicenseType.CC_BY_SA: "CC-BY-SA-4.0",
    }
)

_NOTICE_TEMPLATES: Final[Mapping[LicenseType, str]] = MappingProxyType(
    {
        LicenseType.PUBLIC_DOMAIN: "This work is in the public domain.",
        LicenseType.CC0: "Dedicated to the public domain under CC0 1.0 Universal.",
        LicenseType.CC_BY: "Licensed under CC BY 4.0. Attribution to {authors} is required.",
        LicenseType.CC_BY_SA: "Licensed under CC BY-SA 4.0. Attribution to {authors} and ShareAlike required.",
    }
)

_LICENSE_PRECEDENCE: Final[tuple[LicenseType, ...]] = (
    LicenseType.PUBLIC_DOMAIN,
    LicenseType.CC0,
    LicenseType.CC_BY,
    LicenseType.CC_BY_SA,
)
_LICENSE_RANK: Final[Mapping[LicenseType, int]] = MappingProxyType(
    {license_type: rank for rank, license_type in enumerate(_LICENSE_PRECEDENCE)}
)


def build_license_notice(book: Book) -> str:
    """Return the mandatory license notice for a book."""
    if not isinstance(book, Book):
        raise ValidationError("License notice requires a Book instance")

    template = _NOTICE_TEMPLATES[book.license]
    if not book.license.requires_attribution:
        return template

    author_names = ", ".join(author.full_name for author in book.authors)
    return template.replace(_AUTHORS_PLACEHOLDER, author_names)


def resolve_anthology_license(books: Sequence[Book]) -> LicenseType:
    """Return the license an anthology must carry for all of its books.

    ShareAlike propagates through the whole collection, so a single
    ``CC_BY_SA`` book forces ``CC_BY_SA``. Attribution follows the same rule,
    and permissive books fall back to ``CC0`` or ``PUBLIC_DOMAIN``.
    """
    validated_books = _validate_anthology(books)
    return max((book.license for book in validated_books), key=_LICENSE_RANK.__getitem__)


def _validate_anthology(books: object) -> tuple[Book, ...]:
    if isinstance(books, str | bytes | bytearray) or not isinstance(books, Sequence):
        raise ValidationError("Anthology must be a sequence of Book instances")
    if not books:
        raise LicenseViolationError("Anthology must contain at least one book")

    validated_books: list[Book] = []
    for book in books:
        if not isinstance(book, Book):
            raise ValidationError("Anthology must contain only Book instances")
        validated_books.append(book)
    return tuple(validated_books)
