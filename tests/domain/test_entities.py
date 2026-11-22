"""Tests for the catalog entities and the book aggregate."""

from dataclasses import FrozenInstanceError, replace
from typing import cast

import pytest

from books_api.domain import (
    ISBN,
    Author,
    Book,
    BookAsset,
    BookFormat,
    BookStatus,
    DuplicateAssetError,
    InvalidBookStateError,
    LanguageCode,
    LicenseType,
    ValidationError,
)

_EPUB_CHECKSUM = "a" * 64
_ALT_CHECKSUM = "b" * 64
_PDF_CHECKSUM = "c" * 64
_MOBI_CHECKSUM = "d" * 64
_BLANK_STRINGS = ["", " ", "\t\n", "\u00a0", "\u2003", "\u3000", "\u2028", "\u200b", "\ufeff"]


def make_author(author_id: str = "author-1", full_name: str = "Jane Doe") -> Author:
    return Author(id=author_id, full_name=full_name)


def make_asset(
    book_format: BookFormat = BookFormat.EPUB,
    *,
    size_bytes: int = 1024,
    checksum: str = _EPUB_CHECKSUM,
) -> BookAsset:
    return BookAsset(format=book_format, size_bytes=size_bytes, checksum=checksum)


def make_book(
    *,
    book_id: str = "book-1",
    title: str = "Domain-Driven Design",
    authors: tuple[Author, ...] | None = None,
    isbn: ISBN | None = None,
    license_: LicenseType = LicenseType.CC_BY,
) -> Book:
    return Book(
        id=book_id,
        title=title,
        language=LanguageCode("en"),
        license=license_,
        authors=(make_author(),) if authors is None else authors,
        isbn=isbn,
    )


def test_book_status_exposes_lifecycle_values() -> None:
    assert {member.value for member in BookStatus} == {"draft", "published", "withdrawn"}


def test_author_normalizes_id_and_full_name() -> None:
    author = Author(id="  author-1  ", full_name="  Jane Doe  ")

    assert author.id == "author-1"
    assert author.full_name == "Jane Doe"


@pytest.mark.parametrize("author_id", _BLANK_STRINGS)
def test_author_rejects_empty_id(author_id: str) -> None:
    with pytest.raises(ValidationError, match="Author id"):
        Author(id=author_id, full_name="Jane Doe")


@pytest.mark.parametrize("full_name", _BLANK_STRINGS)
def test_author_rejects_empty_full_name(full_name: str) -> None:
    with pytest.raises(ValidationError, match="full name"):
        Author(id="author-1", full_name=full_name)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", None),
        ("id", 1),
        ("id", b"author-1"),
        ("full_name", None),
        ("full_name", 42),
        ("full_name", ["Jane Doe"]),
    ],
)
def test_author_rejects_non_string_fields(field: str, value: object) -> None:
    with pytest.raises(ValidationError, match="must be a string"):
        replace(make_author(), **{field: value})


def test_author_is_frozen_and_slotted() -> None:
    author = make_author()
    attribute = "full_name"

    with pytest.raises(FrozenInstanceError):
        setattr(author, attribute, "Other Name")

    assert not hasattr(author, "__dict__")


def test_book_asset_accepts_valid_values() -> None:
    asset = make_asset(size_bytes=2048)

    assert asset.format is BookFormat.EPUB
    assert asset.size_bytes == 2048
    assert asset.checksum == _EPUB_CHECKSUM


def test_book_asset_normalizes_checksum_case_and_whitespace() -> None:
    asset = BookAsset(format=BookFormat.PDF, size_bytes=10, checksum=f"  {'A' * 64}  ")

    assert asset.checksum == "a" * 64


@pytest.mark.parametrize("size_bytes", [0, -1, -1024])
def test_book_asset_rejects_non_positive_size(size_bytes: int) -> None:
    with pytest.raises(ValidationError, match="positive"):
        make_asset(size_bytes=size_bytes)


@pytest.mark.parametrize("size_bytes", [1.0, 1024.5, True, "1024", None])
def test_book_asset_rejects_non_integer_size(size_bytes: object) -> None:
    with pytest.raises(ValidationError, match="positive integer"):
        replace(make_asset(), size_bytes=size_bytes)


@pytest.mark.parametrize("book_format", ["epub", "pdf", 1, None])
def test_book_asset_rejects_non_enum_format(book_format: object) -> None:
    with pytest.raises(ValidationError, match="BookFormat"):
        replace(make_asset(), format=book_format)


@pytest.mark.parametrize(
    "checksum",
    [
        "",
        " ",
        "a" * 63,
        "a" * 65,
        "g" * 64,
        f"sha256:{'a' * 64}",
        f"{'a' * 63}-",
    ],
)
def test_book_asset_rejects_invalid_checksum(checksum: str) -> None:
    with pytest.raises(ValidationError, match="SHA-256"):
        make_asset(checksum=checksum)


@pytest.mark.parametrize("checksum", [None, 1, b"a" * 64])
def test_book_asset_rejects_non_string_checksum(checksum: object) -> None:
    with pytest.raises(ValidationError, match="checksum must be a string"):
        replace(make_asset(), checksum=checksum)


def test_book_asset_is_frozen_and_slotted() -> None:
    asset = make_asset()
    attribute = "size_bytes"

    with pytest.raises(FrozenInstanceError):
        setattr(asset, attribute, 1)

    assert not hasattr(asset, "__dict__")


def test_book_defaults_to_draft_without_assets_or_isbn() -> None:
    book = make_book()

    assert book.status is BookStatus.DRAFT
    assert book.assets == ()
    assert book.isbn is None
    assert book.is_downloadable is False
    assert book.available_formats() == frozenset()


def test_book_accepts_multiple_authors_and_isbn() -> None:
    book = make_book(
        authors=(make_author("author-1", "Alice"), make_author("author-2", "Bob")),
        isbn=ISBN("9780306406157"),
    )

    assert [author.id for author in book.authors] == ["author-1", "author-2"]
    assert book.isbn == ISBN("9780306406157")


@pytest.mark.parametrize("license_", list(LicenseType))
def test_book_accepts_every_free_license(license_: LicenseType) -> None:
    book = make_book(license_=license_)

    assert book.license is license_


def test_book_normalizes_id_and_title() -> None:
    book = make_book(book_id="  book-1  ", title="  Domain-Driven Design  ")

    assert book.id == "book-1"
    assert book.title == "Domain-Driven Design"


@pytest.mark.parametrize("title", _BLANK_STRINGS)
def test_book_rejects_empty_title(title: str) -> None:
    with pytest.raises(ValidationError, match="title"):
        make_book(title=title)


@pytest.mark.parametrize("book_id", _BLANK_STRINGS)
def test_book_rejects_empty_id(book_id: str) -> None:
    with pytest.raises(ValidationError, match="Book id"):
        make_book(book_id=book_id)


def test_book_rejects_missing_authors() -> None:
    with pytest.raises(ValidationError, match="at least one author"):
        make_book(authors=())


def test_book_rejects_duplicate_author_ids() -> None:
    with pytest.raises(ValidationError, match="unique by id"):
        make_book(authors=(make_author("author-1"), make_author("author-1", "Other Name")))


def test_book_rejects_duplicate_author_ids_after_normalization() -> None:
    with pytest.raises(ValidationError, match="unique by id"):
        make_book(authors=(make_author("author-1"), make_author("  author-1  ")))


def test_book_allows_unicode_title_and_author_name() -> None:
    book = make_book(title="Война и мир", authors=(make_author("author-1", "Лев Толстой"),))

    assert book.title == "Война и мир"
    assert book.authors[0].full_name == "Лев Толстой"


def test_book_rejects_duplicate_asset_formats_on_creation() -> None:
    assets = (make_asset(), make_asset(checksum=_ALT_CHECKSUM))

    with pytest.raises(DuplicateAssetError, match="same format"):
        replace(make_book(), assets=assets)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("id", 1, "Book id must be a string"),
        ("title", None, "Book title must be a string"),
        ("language", "en", "LanguageCode"),
        ("license", "cc-by", "LicenseType"),
        ("status", "published", "BookStatus"),
        ("isbn", "9780306406157", "ISBN"),
        ("withdrawal_reason", 42, "Withdrawal reason must be a string"),
        ("authors", "Jane Doe", "iterable of Author"),
        ("authors", ("Jane Doe",), "only Author"),
        ("assets", "epub", "iterable of BookAsset"),
        ("assets", ("epub",), "only BookAsset"),
    ],
)
def test_book_rejects_invalid_composition(field: str, value: object, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        replace(make_book(), **{field: value})


def test_book_copies_mutable_author_and_asset_collections() -> None:
    authors = [make_author()]
    assets = [make_asset()]
    book = replace(make_book(), authors=authors, assets=assets)

    authors.append(make_author("author-2", "John Doe"))
    assets.append(make_asset(BookFormat.PDF, checksum=_PDF_CHECKSUM))

    assert book.authors == (make_author(),)
    assert book.assets == (make_asset(),)


def test_book_rejects_published_status_without_assets() -> None:
    with pytest.raises(InvalidBookStateError, match="at least one asset"):
        replace(make_book(), status=BookStatus.PUBLISHED)


def test_book_rejects_withdrawn_status_without_reason() -> None:
    with pytest.raises(InvalidBookStateError, match="withdrawal reason"):
        replace(make_book(), status=BookStatus.WITHDRAWN)


@pytest.mark.parametrize("reason", _BLANK_STRINGS)
def test_book_rejects_withdrawn_status_with_blank_reason(reason: str) -> None:
    with pytest.raises(InvalidBookStateError, match="withdrawal reason"):
        replace(make_book(), status=BookStatus.WITHDRAWN, withdrawal_reason=reason)


def test_book_rejects_withdrawal_reason_for_non_withdrawn_status() -> None:
    with pytest.raises(ValidationError, match="Only withdrawn"):
        replace(make_book(), withdrawal_reason="Rights changed")


def test_book_can_be_restored_as_withdrawn() -> None:
    book = replace(
        make_book().add_asset(make_asset()),
        status=BookStatus.WITHDRAWN,
        withdrawal_reason="  Rights changed  ",
    )

    assert book.status is BookStatus.WITHDRAWN
    assert book.withdrawal_reason == "Rights changed"
    assert book.is_downloadable is False


def test_book_is_frozen_and_slotted() -> None:
    book = make_book()
    attribute = "title"

    with pytest.raises(FrozenInstanceError):
        setattr(book, attribute, "Other Title")

    assert not hasattr(book, "__dict__")


def test_add_asset_returns_new_book_with_the_asset() -> None:
    book = make_book()
    asset = make_asset()

    updated = book.add_asset(asset)

    assert updated.assets == (asset,)
    assert updated.available_formats() == frozenset({BookFormat.EPUB})
    assert book.assets == ()


def test_add_asset_supports_multiple_formats() -> None:
    epub = make_asset()
    pdf = make_asset(BookFormat.PDF, checksum=_PDF_CHECKSUM)

    updated = make_book().add_asset(epub).add_asset(pdf)

    assert updated.assets == (epub, pdf)
    assert updated.available_formats() == frozenset({BookFormat.EPUB, BookFormat.PDF})


def test_add_asset_rejects_duplicate_format_without_replacement() -> None:
    book = make_book().add_asset(make_asset())

    with pytest.raises(DuplicateAssetError, match="already has an asset"):
        book.add_asset(make_asset(checksum=_ALT_CHECKSUM))


@pytest.mark.parametrize("asset", [None, "epub", {"format": "epub"}])
def test_add_asset_rejects_non_asset(asset: object) -> None:
    with pytest.raises(ValidationError, match="BookAsset instance"):
        make_book().add_asset(cast("BookAsset", asset))


@pytest.mark.parametrize("replace_existing", [1, "yes", None])
def test_add_asset_rejects_non_boolean_replace_existing(replace_existing: object) -> None:
    book = make_book().add_asset(make_asset())

    with pytest.raises(ValidationError, match="replace_existing"):
        book.add_asset(
            make_asset(checksum=_ALT_CHECKSUM),
            replace_existing=cast("bool", replace_existing),
        )


def test_add_asset_replaces_existing_format_explicitly() -> None:
    original = make_asset()
    replacement = make_asset(checksum=_ALT_CHECKSUM)
    book = make_book().add_asset(original)

    updated = book.add_asset(replacement, replace_existing=True)

    assert updated.assets == (replacement,)
    assert book.assets == (original,)


def test_replace_asset_preserves_other_formats_order() -> None:
    epub = make_asset()
    pdf = make_asset(BookFormat.PDF, checksum=_PDF_CHECKSUM)
    mobi = make_asset(BookFormat.MOBI, checksum=_MOBI_CHECKSUM)
    replacement = make_asset(checksum=_ALT_CHECKSUM)
    book = make_book().add_asset(epub).add_asset(pdf).add_asset(mobi)

    updated = book.add_asset(replacement, replace_existing=True)

    assert updated.assets == (replacement, pdf, mobi)


def test_replace_existing_adds_missing_format() -> None:
    pdf = make_asset(BookFormat.PDF, checksum=_PDF_CHECKSUM)

    updated = make_book().add_asset(pdf, replace_existing=True)

    assert updated.assets == (pdf,)


def test_add_asset_is_allowed_for_published_book() -> None:
    published = make_book().add_asset(make_asset()).publish()
    pdf = make_asset(BookFormat.PDF, checksum=_PDF_CHECKSUM)

    updated = published.add_asset(pdf)

    assert updated.status is BookStatus.PUBLISHED
    assert updated.is_downloadable is True
    assert updated.available_formats() == frozenset({BookFormat.EPUB, BookFormat.PDF})


def test_replace_asset_is_allowed_for_published_book() -> None:
    published = make_book().add_asset(make_asset()).publish()
    replacement = make_asset(checksum=_ALT_CHECKSUM)

    updated = published.add_asset(replacement, replace_existing=True)

    assert updated.status is BookStatus.PUBLISHED
    assert updated.assets == (replacement,)


@pytest.mark.parametrize("replace_existing", [False, True])
def test_add_asset_is_forbidden_for_withdrawn_book(*, replace_existing: bool) -> None:
    withdrawn = make_book().add_asset(make_asset()).publish().withdraw("Rights changed")

    with pytest.raises(InvalidBookStateError, match="withdrawn"):
        withdrawn.add_asset(make_asset(checksum=_ALT_CHECKSUM), replace_existing=replace_existing)


def test_publish_moves_draft_with_asset_to_published() -> None:
    book = make_book().add_asset(make_asset())

    published = book.publish()

    assert published.status is BookStatus.PUBLISHED
    assert published.is_downloadable is True
    assert book.status is BookStatus.DRAFT
    assert book.is_downloadable is False


def test_publish_rejects_book_without_assets() -> None:
    with pytest.raises(InvalidBookStateError, match="without assets"):
        make_book().publish()


def test_publish_rejects_already_published_book() -> None:
    published = make_book().add_asset(make_asset()).publish()

    with pytest.raises(InvalidBookStateError, match="published"):
        published.publish()


def test_publish_rejects_withdrawn_book() -> None:
    withdrawn = make_book().add_asset(make_asset()).publish().withdraw("Rights changed")

    with pytest.raises(InvalidBookStateError, match="withdrawn"):
        withdrawn.publish()


def test_withdraw_moves_published_book_to_withdrawn() -> None:
    published = make_book().add_asset(make_asset()).publish()

    withdrawn = published.withdraw("Правообладатель уточнил статус")

    assert withdrawn.status is BookStatus.WITHDRAWN
    assert withdrawn.withdrawal_reason == "Правообладатель уточнил статус"
    assert withdrawn.is_downloadable is False
    assert withdrawn.assets == published.assets
    assert published.status is BookStatus.PUBLISHED
    assert published.is_downloadable is True


def test_withdraw_normalizes_reason() -> None:
    published = make_book().add_asset(make_asset()).publish()

    withdrawn = published.withdraw("  Rights changed  ")

    assert withdrawn.withdrawal_reason == "Rights changed"


@pytest.mark.parametrize("reason", _BLANK_STRINGS)
def test_withdraw_rejects_empty_reason(reason: str) -> None:
    published = make_book().add_asset(make_asset()).publish()

    with pytest.raises(ValidationError, match="reason"):
        published.withdraw(reason)


@pytest.mark.parametrize("reason", [None, 42, b"Rights changed"])
def test_withdraw_rejects_non_string_reason(reason: object) -> None:
    published = make_book().add_asset(make_asset()).publish()

    with pytest.raises(ValidationError, match="must be a string"):
        published.withdraw(cast("str", reason))


def test_withdraw_rejects_draft_book() -> None:
    with pytest.raises(InvalidBookStateError, match="draft"):
        make_book().withdraw("Rights changed")


def test_withdraw_rejects_already_withdrawn_book() -> None:
    withdrawn = make_book().add_asset(make_asset()).publish().withdraw("Rights changed")

    with pytest.raises(InvalidBookStateError, match="withdrawn"):
        withdrawn.withdraw("Rights changed again")
