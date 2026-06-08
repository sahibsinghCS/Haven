"""Request identity: authenticated user and optional room label."""

from __future__ import annotations

import re
from contextvars import ContextVar

_ROOM_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_room_id: ContextVar[str] = ContextVar("haven_room_id", default="default")
_user_id: ContextVar[str | None] = ContextVar("haven_user_id", default=None)
_user_email: ContextVar[str | None] = ContextVar("haven_user_email", default=None)


def normalize_room_id(raw: str | None, *, fallback: str = "default") -> str:
    value = (raw or "").strip() or fallback
    if not _ROOM_ID_RE.match(value):
        raise ValueError(
            "Room id must be 1–64 characters: letters, numbers, dots, dashes, underscores."
        )
    return value


def get_room_id() -> str:
    return _room_id.get()


def set_room_id(room_id: str) -> None:
    _room_id.set(normalize_room_id(room_id))


def get_user_id() -> str | None:
    return _user_id.get()


def get_user_email() -> str | None:
    return _user_email.get()


def set_user(user_id: str, email: str | None = None) -> None:
    uid = (user_id or "").strip()
    if not uid or not _UUID_RE.match(uid):
        raise ValueError("Invalid user id")
    _user_id.set(uid)
    if email:
        _user_email.set(email.strip())


def clear_user() -> None:
    _user_id.set(None)
    _user_email.set(None)


def storage_slug() -> str:
    """Filesystem path segment for local JSON backup."""
    uid = get_user_id()
    if uid:
        return f"users/{uid}"
    return f"rooms/{get_room_id()}"


def is_authenticated() -> bool:
    return bool(get_user_id())
