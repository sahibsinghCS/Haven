"""Load/save preferences + publish UI events."""

from __future__ import annotations

from typing import Any, Optional

from roomos.preferences.apply import PreferenceApplyResult, PreferenceChangeSpec, apply_preference_changes
from roomos.preferences.document import PreferenceValidationError, ROOM_STATE_ORDER, resolve_active_preset_id
from roomos.preferences.store import save_preferences_document
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


def _active_preset_name(doc: dict[str, Any], active_id: str) -> str:
    preset = next(
        (p for p in doc.get("presets", []) if isinstance(p, dict) and str(p.get("id")) == active_id),
        None,
    )
    return str(preset.get("name", active_id)) if isinstance(preset, dict) else active_id


def sync_preferences_to_devices(*, room_state: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Push the saved preset for the current mood to connected devices immediately."""
    from roomos.devices.scene_apply import (
        apply_preference_scene,
        has_controllable_devices,
        preference_sync_dry_run,
        resolve_apply_scene_for_mood,
    )
    from roomos.integrations.device_bridge import merge_runtime_integrations

    if not has_controllable_devices():
        return None

    mood = str(room_state or "").strip()
    if not mood:
        snap = state.hub.latest
        if snap is not None:
            mood = str(snap.primary_state or "").strip()
    if mood not in ROOM_STATE_ORDER:
        return None

    actions_dry_run = True
    integrations: dict[str, Any] = {}
    engine = state.engine
    actions = getattr(engine, "_actions", None) if engine is not None else None
    if actions is not None:
        actions_dry_run = bool(actions.dry_run)
        integrations = dict(actions.integrations or {})
    if not integrations:
        integrations = merge_runtime_integrations({})

    pref_dry_run = preference_sync_dry_run(actions_dry_run)
    scene = resolve_apply_scene_for_mood(mood)
    record = apply_preference_scene(
        scene,
        dry_run=pref_dry_run,
        integrations=integrations,
        room_state=mood,
    )
    if engine is not None:
        engine._preferences_cache = ("", {})
    log.info(
        "[preference_sync] applied saved preferences for mood=%s dry_run=%s",
        mood,
        pref_dry_run,
    )
    return record


def save_preferences(doc: dict[str, Any], *, source: str = "web") -> dict[str, Any]:
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

    active_id = resolve_active_preset_id(saved)
    event = PreferencesEvent(
        source=source,
        updated_at=str(saved.get("updatedAt", "")),
        active_preset_id=active_id,
        preset_name=_active_preset_name(saved, active_id),
        target_states=[],
        changes=["preferences document updated"],
        notes="",
    )
    state.preferences_hub.publish_from_thread(event)

    try:
        sync_preferences_to_devices()
    except Exception as e:
        log.warning("Preference device sync after save failed: %s", e)

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
    saved = save_preferences(result.doc, source=source)

    # save_preferences publishes a generic event; replace with the richer Telegram payload.
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
