"""Load/save preferences + publish UI events."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roomos.preferences.apply import PreferenceApplyResult, PreferenceChangeSpec, apply_preference_changes
from roomos.preferences.document import PreferenceValidationError, resolve_active_preset_id
from roomos.preferences.store import read_preferences_document, save_preferences_document
from roomos.utils.logging import get_logger

from .persistence import load_json_document, save_json_document
from .preferences_store import DEFAULT_PREFERENCES_DOC, preferences_store_path
from .core.preferences_events import PreferencesEvent
from .core.state import state
from roomos.preferences.document import normalize_preference_document

log = get_logger("roomos.preferences.service")


def load_preferences() -> dict[str, Any]:
    def _default() -> dict[str, Any]:
        return dict(DEFAULT_PREFERENCES_DOC)

    def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
        try:
            return normalize_preference_document(raw)
        except Exception as e:
            log.warning("Preferences normalize failed (%s); using defaults.", e)
            return _default()

    return load_json_document(
        "preferences",
        default_fn=_default,
        normalize_fn=_normalize,
        local_filename="preferences.json",
    )


def save_preferences(doc: dict[str, Any]) -> dict[str, Any]:
    def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
        return normalize_preference_document(raw)

    saved = save_json_document(
        "preferences",
        doc,
        normalize_fn=_normalize,
        local_filename="preferences.json",
    )
    # Keep canonical on-disk format via existing helper when using default room
    try:
        from .room_context import get_user_id

        if not get_user_id():
            save_preferences_document(preferences_store_path(), saved)
    except Exception:
        pass
    return saved


def apply_and_save_preferences(
    spec: PreferenceChangeSpec,
    *,
    source: str,
    notes: str,
    fallback_state: str | None,
) -> PreferenceApplyResult:
    doc = load_preferences()
    active_id = resolve_active_preset_id(doc)
    preset = next(
        (p for p in doc.get("presets", []) if isinstance(p, dict) and str(p.get("id")) == active_id),
        None,
    )
    preset_name = str(preset.get("name", active_id)) if isinstance(preset, dict) else active_id

    result = apply_preference_changes(doc, spec, fallback_state=fallback_state)
    saved = save_preferences(result.doc)

    event = PreferencesEvent(
        source=source,
        updated_at=str(saved.get("updatedAt", "")),
        active_preset_id=result.active_preset_id,
        preset_name=result.preset_name,
        target_states=result.target_states,
        changes=result.changes,
        notes=notes,
    )
    state.preferences_hub.publish_from_thread(event)
    log.info("Preferences updated via %s: %s", source, "; ".join(result.changes))
    return result
