"""Runtime guards that keep domain invariants independent of static typing."""

from collections.abc import Iterable
from typing import cast

from books_api.domain.errors import ValidationError


def ensure_str(value: object, message: str) -> str:
    """Return the value when it is text, otherwise raise a domain error."""
    if not isinstance(value, str):
        raise ValidationError(message)
    return value


def ensure_required_text(value: object, subject: str) -> str:
    """Return stripped text with at least one printable character, otherwise raise a domain error."""
    text = ensure_str(value, f"{subject} must be a string").strip()
    if not has_visible_text(text):
        raise ValidationError(f"{subject} must contain visible characters")
    return text


def has_visible_text(text: str) -> bool:
    """Return whether text contains at least one printable character."""
    return any(character.isprintable() for character in text)


def ensure_positive_int(value: object, message: str) -> int:
    """Return the value when it is a strictly positive integer, otherwise raise a domain error."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError(message)
    return value


def ensure_iterable(value: object, message: str) -> Iterable[object]:
    """Return the value when it is a non-text iterable, otherwise raise a domain error.

    A bare string is rejected on purpose: iterating it would silently split an
    identifier into characters instead of yielding collection items.
    """
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise ValidationError(message)
    return cast("Iterable[object]", value)
