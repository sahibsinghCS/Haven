"""Mood registry — the dynamic room-state taxonomy stored in ``data/moods.json``.

Replaces the fixed 4-mood preference taxonomy. Each mood is either one of the
four restorable builtins (away / sleep / work / relaxing) or a user-defined
custom mood with its own on-device training dataset.

``gaming`` is intentionally NOT a mood: it remains a legacy inference-only
label (still allowed in live predictions while the active model bundle knows
it) but can never be created, restored, or given preferences.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.logging import get_logger

log = get_logger("roomos.moods.registry")

# Display names for the 4 restorable preloaded moods (order = UI order).
BUILTIN_MOODS: Dict[str, str] = {
    "sleep": "Sleep",
    "work": "Work / Studying",
    "relaxing": "Relaxing",
    "away": "Away",
}

# Labels the live model may predict that are not user-manageable moods.
LEGACY_INFERENCE_ONLY: tuple[str, ...] = ("gaming",)

ML_STATUSES = ("untrained", "collecting", "training", "ready", "error")

SCHEMA_VERSION = 1

# Resolved lazily so tests can monkeypatch. backend/roomos/moods/registry.py
# -> parents[2] == backend/.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_lock = threading.RLock()
_cache: tuple[str, float, dict] | None = None  # (path, mtime, doc) for default path only


class MoodRegistryError(RuntimeError):
    """Registry could not be read or written."""


class MoodValidationError(ValueError):
    """Invalid mood create/delete request."""


def default_moods_path() -> Path:
    return _BACKEND_DIR / "data" / "moods.json"


def registry_exists(path: Optional[Path] = None) -> bool:
    """True once the dynamic mood registry has been created (post-migration)."""
    p = Path(path) if path is not None else default_moods_path()
    return p.is_file()


def datasets_root() -> Path:
    return _BACKEND_DIR / "data" / "personal_datasets"


def training_jobs_root() -> Path:
    return _BACKEND_DIR / "data" / "personal_training_jobs"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return slug[:40]


def _default_ml() -> dict:
    return {
        "enabled": True,
        "status": "untrained",
        "frameCount": 0,
        "burstCount": 0,
        "lastTrainedAt": None,
    }


def _builtin_mood(key: str, *, ml_status: str = "untrained") -> dict:
    now = _now_iso()
    ml = _default_ml()
    ml["status"] = ml_status
    return {
        "id": key,
        "displayName": BUILTIN_MOODS[key],
        "kind": "builtin",
        "builtinKey": key,
        "createdAt": now,
        "updatedAt": now,
        "ml": ml,
    }


def _bundle_classes() -> List[str]:
    """Classes of the currently deployed model bundle (best effort)."""
    try:
        bundle = _BACKEND_DIR / "data" / "models" / "latest" / "label_encoder.json"
        data = json.loads(bundle.read_text(encoding="utf-8"))
        return [str(c) for c in data.get("classes", [])]
    except Exception:
        return []


def _migrated_registry() -> dict:
    """First-run migration: the fixed 4 moods become builtin registry entries."""
    classes = set(_bundle_classes())
    moods = [
        _builtin_mood(key, ml_status="ready" if key in classes else "untrained")
        for key in BUILTIN_MOODS
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "updatedAt": _now_iso(),
        "consent": {"accepted": False, "acceptedAt": None},
        "moods": moods,
    }


def _normalize(doc: dict) -> dict:
    out = dict(doc)
    out["schemaVersion"] = SCHEMA_VERSION
    moods = out.get("moods")
    if not isinstance(moods, list):
        moods = []
    normalized: List[dict] = []
    seen: set[str] = set()
    for m in moods:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("id") or "").strip()
        if not mid or mid in seen or mid in LEGACY_INFERENCE_ONLY:
            continue
        seen.add(mid)
        entry = dict(m)
        entry["id"] = mid
        entry["displayName"] = str(m.get("displayName") or mid.replace("_", " ").title())
        kind = str(m.get("kind") or ("builtin" if mid in BUILTIN_MOODS else "custom"))
        entry["kind"] = kind if kind in ("builtin", "custom") else "custom"
        if entry["kind"] == "builtin":
            entry["builtinKey"] = str(m.get("builtinKey") or mid)
        ml = m.get("ml") if isinstance(m.get("ml"), dict) else {}
        merged_ml = _default_ml()
        merged_ml.update({k: v for k, v in ml.items() if k in merged_ml})
        if merged_ml["status"] not in ML_STATUSES:
            merged_ml["status"] = "untrained"
        entry["ml"] = merged_ml
        entry.setdefault("createdAt", _now_iso())
        entry.setdefault("updatedAt", entry["createdAt"])
        normalized.append(entry)
    out["moods"] = normalized
    consent = out.get("consent") if isinstance(out.get("consent"), dict) else {}
    out["consent"] = {
        "accepted": bool(consent.get("accepted", False)),
        "acceptedAt": consent.get("acceptedAt"),
    }
    return out


def load_registry(path: Optional[Path] = None) -> dict:
    """Read (and lazily migrate) the mood registry."""
    global _cache
    p = Path(path) if path is not None else default_moods_path()
    with _lock:
        if path is None:
            try:
                mtime = p.stat().st_mtime if p.exists() else -1.0
            except OSError:
                mtime = -1.0
            if (
                _cache is not None
                and _cache[0] == str(p)
                and _cache[1] == mtime
                and mtime > 0
            ):
                return json.loads(json.dumps(_cache[2]))  # defensive copy
        if not p.exists():
            doc = _migrated_registry()
            _write(p, doc)
            log.info("Migrated fixed moods into registry -> %s", p)
        else:
            try:
                doc = _normalize(json.loads(p.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError) as e:
                raise MoodRegistryError(f"Could not read mood registry {p}: {e}") from e
        if path is None:
            try:
                _cache = (str(p), p.stat().st_mtime, json.loads(json.dumps(doc)))
            except OSError:
                _cache = None
        return doc


def save_registry(doc: dict, path: Optional[Path] = None) -> dict:
    global _cache
    p = Path(path) if path is not None else default_moods_path()
    with _lock:
        out = _normalize(doc)
        out["updatedAt"] = _now_iso()
        _write(p, out)
        if path is None:
            try:
                _cache = (str(p), p.stat().st_mtime, json.loads(json.dumps(out)))
            except OSError:
                _cache = None
        return out


def _write(p: Path, doc: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    tmp.replace(p)


# --- queries ----------------------------------------------------------------


def get_mood(mood_id: str, path: Optional[Path] = None) -> Optional[dict]:
    doc = load_registry(path)
    for m in doc["moods"]:
        if m["id"] == mood_id:
            return m
    return None


def active_mood_ids(path: Optional[Path] = None) -> List[str]:
    return [m["id"] for m in load_registry(path)["moods"]]


def allowed_live_labels(path: Optional[Path] = None) -> set[str]:
    """Labels live inference may surface: active moods + legacy-only labels."""
    return set(active_mood_ids(path)) | set(LEGACY_INFERENCE_ONLY) | {"unknown"}


def ui_state_order(path: Optional[Path] = None) -> tuple[str, ...]:
    """Dynamic UI/state order: registry order with legacy ``gaming`` kept.

    Reproduces the historic (sleep, gaming, work, relaxing, away) order when
    the registry holds exactly the migrated builtins.
    """
    ids = active_mood_ids(path)
    out = list(ids)
    for legacy in LEGACY_INFERENCE_ONLY:
        if legacy in out:
            continue
        if out and out[0] == "sleep":
            out.insert(1, legacy)
        else:
            out.append(legacy)
    return tuple(out)


def ml_class_candidates(path: Optional[Path] = None) -> List[str]:
    """Moods eligible for the trained class list (ML enabled, not deleted)."""
    doc = load_registry(path)
    return [m["id"] for m in doc["moods"] if m.get("ml", {}).get("enabled", True)]


# --- mutations ---------------------------------------------------------------


def create_mood(
    *,
    name: Optional[str] = None,
    builtin_key: Optional[str] = None,
    path: Optional[Path] = None,
) -> dict:
    """Create a custom mood from ``name`` or restore a deleted builtin."""
    with _lock:
        doc = load_registry(path)
        existing = {m["id"] for m in doc["moods"]}

        if builtin_key is not None:
            key = str(builtin_key).strip().lower()
            if key not in BUILTIN_MOODS:
                raise MoodValidationError(
                    f"Unknown builtin mood {builtin_key!r}. "
                    f"Valid: {', '.join(BUILTIN_MOODS)}."
                )
            if key in existing:
                raise MoodValidationError(f"Mood '{key}' already exists.")
            ml_status = "ready" if key in set(_bundle_classes()) else "untrained"
            mood = _builtin_mood(key, ml_status=ml_status)
        else:
            display = str(name or "").strip()
            if len(display) < 2:
                raise MoodValidationError("Mood name must be at least 2 characters.")
            if len(display) > 40:
                raise MoodValidationError("Mood name must be at most 40 characters.")
            slug = slugify(display)
            if not slug:
                raise MoodValidationError("Mood name must contain letters or numbers.")
            if slug in LEGACY_INFERENCE_ONLY:
                raise MoodValidationError("That mood name is reserved.")
            if slug in BUILTIN_MOODS and slug not in existing:
                # Friendly: "Sleep" typed by hand restores the builtin.
                return create_mood(builtin_key=slug, path=path)
            if slug in existing or slug == "unknown":
                slug = f"custom_{slug}_{uuid.uuid4().hex[:6]}"
            now = _now_iso()
            mood = {
                "id": slug,
                "displayName": display,
                "kind": "custom",
                "createdAt": now,
                "updatedAt": now,
                "ml": _default_ml(),
            }

        doc["moods"].append(mood)
        save_registry(doc, path)
        return mood


def delete_mood(mood_id: str, path: Optional[Path] = None) -> dict:
    """Delete any mood (builtin or custom). Returns the removed entry."""
    with _lock:
        doc = load_registry(path)
        target = next((m for m in doc["moods"] if m["id"] == mood_id), None)
        if target is None:
            raise MoodValidationError(f"Unknown mood: {mood_id!r}")
        if len(doc["moods"]) <= 1:
            raise MoodValidationError("At least one mood must remain.")
        doc["moods"] = [m for m in doc["moods"] if m["id"] != mood_id]
        save_registry(doc, path)
        return target


def update_mood_ml(mood_id: str, path: Optional[Path] = None, **fields: Any) -> dict:
    """Patch ml.* fields for a mood (status, counts, lastTrainedAt...)."""
    with _lock:
        doc = load_registry(path)
        target = next((m for m in doc["moods"] if m["id"] == mood_id), None)
        if target is None:
            raise MoodValidationError(f"Unknown mood: {mood_id!r}")
        ml = dict(target.get("ml") or _default_ml())
        for k, v in fields.items():
            if k in ("enabled", "status", "frameCount", "burstCount", "lastTrainedAt"):
                ml[k] = v
        target["ml"] = ml
        target["updatedAt"] = _now_iso()
        save_registry(doc, path)
        return target


def set_consent(accepted: bool, path: Optional[Path] = None) -> dict:
    with _lock:
        doc = load_registry(path)
        doc["consent"] = {
            "accepted": bool(accepted),
            "acceptedAt": _now_iso() if accepted else None,
        }
        return save_registry(doc, path)
