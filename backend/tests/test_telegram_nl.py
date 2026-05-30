"""Telegram NL helpers (no network)."""

from roomos.integrations.telegram_nl import (
    _keyword_fallback,
    bot_user_id_from_token,
    parse_allowed_chat_ids,
)


def test_parse_allowed_chat_ids():
    assert parse_allowed_chat_ids("111, 222") == frozenset({111, 222})


def test_bot_user_id_from_token():
    assert bot_user_id_from_token("123456:ABC") == 123456
    assert bot_user_id_from_token("bad") is None


def test_keyword_not_sleep_working():
    parsed = _keyword_fallback("I am not sleeping, I am actually working")
    assert parsed is not None
    assert parsed.corrected_label == "work"
