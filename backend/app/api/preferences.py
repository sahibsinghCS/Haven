"""Preferences persistence — matches PreferenceDocument in the frontend."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from roomos.preferences.document import PreferenceValidationError, normalize_preference_document
from roomos.utils.logging import get_logger

from ..preferences_service import load_preferences, save_preferences

log = get_logger("roomos.api.preferences")
router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("")
def get_preferences() -> dict[str, Any]:
    return load_preferences()


@router.put("")
def put_preferences(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict) or "presets" not in doc:
        raise HTTPException(status_code=400, detail="Body must be a PreferenceDocument with 'presets'.")
    try:
        normalize_preference_document(doc)
    except PreferenceValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return save_preferences(doc)
