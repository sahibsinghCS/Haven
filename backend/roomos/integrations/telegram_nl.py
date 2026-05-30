"""Map free-text Telegram messages to RoomOS activity labels."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional, Sequence

ROOM_ACTIVITY_LABELS: tuple[str, ...] = ("work", "sleep", "gaming", "relaxing", "away")

_LABEL_SET = frozenset(ROOM_ACTIVITY_LABELS)


@dataclass(frozen=True)
class TelegramLabelParse:
    corrected_label: str
    needs_clarification: bool = False
    clarification_question: str = ""
    reason: str = ""


def _normalize_label(value: str) -> Optional[str]:
    key = re.sub(r"[^a-z]+", " ", str(value or "").strip().lower()).strip()
    aliases = {
        "working": "work",
        "work": "work",
        "desk": "work",
        "office": "work",
        "sleeping": "sleep",
        "sleep": "sleep",
        "asleep": "sleep",
        "nap": "sleep",
        "game": "gaming",
        "gaming": "gaming",
        "games": "gaming",
        "play": "gaming",
        "relax": "relaxing",
        "relaxing": "relaxing",
        "chill": "relaxing",
        "couch": "relaxing",
        "tv": "relaxing",
        "away": "away",
        "empty": "away",
        "gone": "away",
        "left": "away",
    }
    if key in _LABEL_SET:
        return key
    return aliases.get(key)


def _keyword_fallback(user_text: str) -> Optional[TelegramLabelParse]:
    """Cheap local parse when OpenAI is unavailable."""
    text = user_text.lower()
    if not text.strip():
        return None
    neg_sleep = bool(re.search(r"\bnot\s+sleep", text)) or "not sleeping" in text
    if neg_sleep and re.search(r"\b(work|working|desk)\b", text):
        return TelegramLabelParse(corrected_label="work", reason="keyword: not sleep + work")
    for word, label in (
        ("gaming", "gaming"),
        ("game", "gaming"),
        ("working", "work"),
        ("work", "work"),
        ("sleeping", "sleep"),
        ("sleep", "sleep"),
        ("relaxing", "relaxing"),
        ("away", "away"),
    ):
        if re.search(rf"\b{re.escape(word)}\b", text):
            return TelegramLabelParse(corrected_label=label, reason=f"keyword: {word}")
    return None


async def parse_correction_text(
    user_text: str,
    *,
    predicted_label: Optional[str],
    api_key: str,
    model: str,
) -> TelegramLabelParse:
    """Use OpenAI JSON mode; fall back to keywords on failure."""
    fallback = _keyword_fallback(user_text)
    if not api_key.strip():
        if fallback is not None:
            return fallback
        raise RuntimeError("OPENAI_API_KEY is not set and the message could not be parsed locally.")

    from openai import AsyncOpenAI

    labels = ", ".join(ROOM_ACTIVITY_LABELS)
    system = (
        "You map a user's Haven room-activity correction to exactly one label.\n"
        f"Valid labels only: {labels}.\n"
        "Handle negation and contrast (e.g. 'I wasn't sleeping, I'm actually working' -> work).\n"
        "Prefer the activity they assert over the one they deny.\n"
        "If the message is ambiguous, set needs_clarification true and ask one short question.\n"
        "Respond with JSON only: "
        '{"corrected_label":"<label>","needs_clarification":false,'
        '"clarification_question":"","reason":"<short>"}'
    )
    user = user_text.strip()
    if predicted_label:
        user += f"\n\n(Current model guess: {predicted_label})"

    client = AsyncOpenAI(api_key=api_key.strip())
    try:
        resp = await client.chat.completions.create(
            model=model.strip() or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)
    except Exception:
        if fallback is not None:
            return fallback
        raise

    if bool(data.get("needs_clarification")):
        q = str(data.get("clarification_question") or "Which activity? work, sleep, gaming, relaxing, or away?")
        return TelegramLabelParse(
            corrected_label="",
            needs_clarification=True,
            clarification_question=q,
            reason=str(data.get("reason", "")),
        )

    label = _normalize_label(str(data.get("corrected_label", "")))
    if label is None:
        if fallback is not None:
            return fallback
        return TelegramLabelParse(
            corrected_label="",
            needs_clarification=True,
            clarification_question="Which activity? work, sleep, gaming, relaxing, or away?",
            reason="model returned invalid label",
        )
    return TelegramLabelParse(
        corrected_label=label,
        reason=str(data.get("reason", "")),
    )


def parse_allowed_chat_ids(raw: str) -> frozenset[int]:
    """Comma-separated Telegram chat ids."""
    out: set[int] = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.add(int(part))
    return frozenset(out)


def bot_user_id_from_token(token: str) -> Optional[int]:
    """Leading numeric segment of a BotFather token is the bot id (not your chat id)."""
    head = (token or "").split(":", 1)[0].strip()
    if head.isdigit():
        return int(head)
    return None
