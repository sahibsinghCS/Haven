"""Read/write PreferenceDocument JSON (path supplied by caller)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils.io import read_json, write_json
from .document import normalize_preference_document


def read_preferences_document(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    raw = read_json(path)
    return normalize_preference_document(raw)


def save_preferences_document(path: Path, doc: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_preference_document(doc)
    normalized["updatedAt"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, normalized)
    return normalized
