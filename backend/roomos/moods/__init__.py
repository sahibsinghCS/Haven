"""User-defined mood registry (dynamic room-state taxonomy)."""

from .registry import (
    BUILTIN_MOODS,
    MoodRegistryError,
    MoodValidationError,
    active_mood_ids,
    allowed_live_labels,
    create_mood,
    delete_mood,
    get_mood,
    load_registry,
    save_registry,
    set_consent,
    ui_state_order,
    update_mood_ml,
)

__all__ = [
    "BUILTIN_MOODS",
    "MoodRegistryError",
    "MoodValidationError",
    "active_mood_ids",
    "allowed_live_labels",
    "create_mood",
    "delete_mood",
    "get_mood",
    "load_registry",
    "save_registry",
    "set_consent",
    "ui_state_order",
    "update_mood_ml",
]
