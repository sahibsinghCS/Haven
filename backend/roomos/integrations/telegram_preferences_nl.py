"""OpenAI: natural language → preference edits for Haven."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List, Optional

from roomos.preferences.apply import PreferenceChangeSpec
from roomos.preferences.document import ROOM_STATE_ORDER


@dataclass(frozen=True)
class TelegramPreferenceParse:
    applies: bool
    needs_clarification: bool = False
    clarification_question: str = ""
    spec: Optional[PreferenceChangeSpec] = None
    reason: str = ""


def _keyword_preference_parse(user_text: str) -> Optional[TelegramPreferenceParse]:
    text = user_text.lower()
    pref_hints = (
        "fan",
        "light",
        "brightness",
        "bright",
        "dim",
        "temperature",
        "thermostat",
        "color",
        "colour",
        "preference",
        "preferences",
        "setting",
    )
    if not any(h in text for h in pref_hints):
        return None

    spec = PreferenceChangeSpec(target_states=[])
    for state in ROOM_STATE_ORDER:
        if state in text:
            spec.target_states.append(state)

    if "fan" in text:
        if any(w in text for w in ("off", "lower", "low", "quieter", "disable")):
            spec.fan = "off"
        elif any(w in text for w in ("on", "higher", "high", "enable")):
            spec.fan = "on"

    if any(w in text for w in ("dim", "dimmer", "lower brightness", "less bright")):
        spec.brightness = {"relative": "lower"}
    elif any(w in text for w in ("brighter", "higher brightness", "more bright")):
        spec.brightness = {"relative": "higher"}

    if "blue" in text:
        spec.light_color = {"name": "blue"}
    elif "warm" in text:
        spec.light_color = {"relative": "warmer"}
    elif "cool" in text:
        spec.light_color = {"relative": "cooler"}

    if spec.fan or spec.brightness or spec.light_color:
        return TelegramPreferenceParse(applies=True, spec=spec, reason="keyword preference")
    return None


async def parse_preference_text(
    user_text: str,
    *,
    current_state: Optional[str],
    active_preset_name: str,
    api_key: str,
    model: str,
) -> TelegramPreferenceParse:
    fallback = _keyword_preference_parse(user_text)
    if not api_key.strip():
        return fallback or TelegramPreferenceParse(applies=False)

    from openai import AsyncOpenAI

    states = ", ".join(ROOM_STATE_ORDER)
    system = (
        "You parse Haven smart-room preference commands.\n"
        f"Room states: {states}.\n"
        "If the user wants to change fan, lights, brightness, or temperature, set applies=true.\n"
        "If they are correcting what activity the room thinks (sleep/work/etc), set applies=false.\n"
        "target_states: list of states to edit; empty means the current room state only.\n"
        "fan: on | off | lower | higher | null\n"
        "brightness: null or {{\"absolute\":0-100}} or {{\"delta\":int}} or {{\"relative\":\"lower\"|\"higher\"}}\n"
        "light_color: null or {{\"hex\":\"#RRGGBB\"}} or {{\"name\":\"blue\"|\"warm\"|...}} or {{\"relative\":\"warmer\"|\"cooler\"}}\n"
        "temperature_f: null or {{\"absolute\":60-82}} or {{\"delta\":int}} or {{\"relative\":\"lower\"|\"higher\"|\"warmer\"|\"cooler\"}}\n"
        "JSON only: "
        '{"applies":true,"needs_clarification":false,"clarification_question":"",'
        '"target_states":[],"fan":null,"brightness":null,"light_color":null,"temperature_f":null,"reason":""}'
    )
    user = (
        f"Active preset: {active_preset_name}\n"
        f"Current room state: {current_state or 'unknown'}\n\n"
        f"User message: {user_text.strip()}"
    )

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
        data = json.loads((resp.choices[0].message.content or "").strip())
    except Exception:
        if fallback:
            return fallback
        raise

    if not bool(data.get("applies")):
        return TelegramPreferenceParse(applies=False, reason=str(data.get("reason", "")))

    if bool(data.get("needs_clarification")):
        q = str(
            data.get("clarification_question")
            or "Which setting? fan, light color, brightness, or temperature?"
        )
        return TelegramPreferenceParse(applies=True, needs_clarification=True, clarification_question=q)

    target_states = [str(s) for s in (data.get("target_states") or []) if str(s) in ROOM_STATE_ORDER]
    spec = PreferenceChangeSpec(
        target_states=target_states,
        fan=data.get("fan") if data.get("fan") is not None else None,
        brightness=data.get("brightness") if isinstance(data.get("brightness"), dict) else None,
        light_color=data.get("light_color") if isinstance(data.get("light_color"), dict) else None,
        temperature_f=data.get("temperature_f") if isinstance(data.get("temperature_f"), dict) else None,
    )
    if not any((spec.fan, spec.brightness, spec.light_color, spec.temperature_f)):
        if fallback:
            return fallback
        return TelegramPreferenceParse(
            applies=True,
            needs_clarification=True,
            clarification_question="What should I change — fan, light, brightness, or temperature?",
        )
    return TelegramPreferenceParse(applies=True, spec=spec, reason=str(data.get("reason", "")))
