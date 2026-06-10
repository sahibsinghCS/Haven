"""Mood registry, on-device dataset collection, and personal training API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from roomos.moods import registry as mood_registry
from roomos.training import personal_dataset as pds
from roomos.training.collection import mood_collection
from roomos.training.personal_trainer import (
    PersonalTrainingError,
    personal_training_jobs,
)
from roomos.utils.logging import get_logger

from ..core.state import state

log = get_logger("roomos.app.api.moods")

router = APIRouter(prefix="/api/moods", tags=["moods"])
training_router = APIRouter(prefix="/api/training", tags=["training"])


# --- payload models ----------------------------------------------------------


class CreateMoodRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    builtinKey: Optional[str] = None


class CollectionStartRequest(BaseModel):
    durationSec: float = Field(default=300.0, ge=10.0, le=3600.0)


class ConsentRequest(BaseModel):
    accepted: bool


# --- helpers ------------------------------------------------------------------


def _mood_payload(mood: dict) -> dict:
    out = dict(mood)
    counts = pds.dataset_counts(mood_registry.datasets_root(), mood["id"])
    ml = dict(out.get("ml") or {})
    ml["burstCount"] = counts["burstCount"]
    ml["frameCount"] = counts["frameCount"]
    out["ml"] = ml
    return out


def _require_mood(mood_id: str) -> dict:
    mood = mood_registry.get_mood(mood_id)
    if mood is None:
        raise HTTPException(status_code=404, detail=f"Unknown mood: {mood_id!r}")
    return mood


def _collection_payload(mood_id: Optional[str] = None) -> dict:
    status = mood_collection.status()
    if status is not None and mood_id is not None and status.get("moodId") != mood_id:
        status = None
    payload: Dict[str, Any] = {"session": status}
    if mood_id is not None:
        counts = pds.dataset_counts(mood_registry.datasets_root(), mood_id)
        payload["dataset"] = counts
        payload["minimums"] = {
            "bursts": pds.MIN_BURSTS_TO_TRAIN,
            "frames": pds.MIN_FRAMES_TO_TRAIN,
        }
        payload["readyToTrain"] = (
            counts["burstCount"] >= pds.MIN_BURSTS_TO_TRAIN
            and counts["frameCount"] >= pds.MIN_FRAMES_TO_TRAIN
        )
    return payload


def _hot_reload_engine() -> None:
    engine = state.engine
    if engine is not None and engine.is_running():
        engine.reload_model_bundle()
        log.info("Live engine hot-reloaded after personal training.")


# --- mood CRUD ------------------------------------------------------------------


@router.get("")
def list_moods() -> dict:
    doc = mood_registry.load_registry()
    deleted_builtins = [
        {"builtinKey": key, "displayName": name}
        for key, name in mood_registry.BUILTIN_MOODS.items()
        if not any(m["id"] == key for m in doc["moods"])
    ]
    return {
        "moods": [_mood_payload(m) for m in doc["moods"]],
        "restorableBuiltins": deleted_builtins,
        "consent": doc.get("consent", {"accepted": False}),
        "datasetFolder": str(mood_registry.datasets_root()),
        "collection": mood_collection.status(),
        "trainingActive": personal_training_jobs.is_running(),
    }


@router.post("", status_code=201)
def create_mood(payload: CreateMoodRequest) -> dict:
    try:
        mood = mood_registry.create_mood(
            name=payload.name,
            builtin_key=payload.builtinKey,
        )
    except mood_registry.MoodValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"mood": _mood_payload(mood)}


@router.delete("/{mood_id}")
def delete_mood(
    mood_id: str,
    deleteData: bool = Query(default=False),
) -> dict:
    if mood_collection.active_mood_id() == mood_id:
        mood_collection.stop(reason="user")
    try:
        removed = mood_registry.delete_mood(mood_id)
    except mood_registry.MoodValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Drop the mood from every preset's preference matrix.
    try:
        from ..preferences_service import load_preferences, save_preferences

        doc = load_preferences()
        changed = False
        for preset in doc.get("presets", []):
            prefs = preset.get("preferences")
            if isinstance(prefs, dict) and mood_id in prefs:
                prefs.pop(mood_id, None)
                changed = True
        if changed:
            save_preferences(doc)
    except Exception as e:
        log.warning("Could not remove '%s' from preferences: %s", mood_id, e)

    data_deleted = False
    if deleteData:
        import shutil

        target = pds.mood_dataset_dir(mood_registry.datasets_root(), mood_id)
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            data_deleted = True

    # Mask the deleted label immediately (no retrain needed to hide it).
    engine = state.engine
    if engine is not None and engine.is_running():
        try:
            engine.reload_model_bundle()
        except Exception as e:
            log.warning("Engine label refresh after delete failed: %s", e)

    return {"deleted": removed["id"], "dataDeleted": data_deleted}


# --- collection -------------------------------------------------------------------


@router.post("/{mood_id}/collection/start")
def start_collection(mood_id: str, payload: CollectionStartRequest) -> dict:
    _require_mood(mood_id)
    doc = mood_registry.load_registry()
    if not doc.get("consent", {}).get("accepted"):
        raise HTTPException(
            status_code=409,
            detail="Privacy consent required before collecting camera data.",
        )
    if state.live_mode != "live" or not state.is_running:
        raise HTTPException(
            status_code=409,
            detail="Live camera is not running. Start the camera on the Live page first.",
        )
    if personal_training_jobs.is_running():
        raise HTTPException(
            status_code=409,
            detail="A training job is running. Wait for it to finish first.",
        )
    try:
        session = mood_collection.start(
            mood_id,
            payload.durationSec,
            mood_registry.datasets_root(),
        )
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    mood_registry.update_mood_ml(mood_id, status="collecting")
    return {"session": session, **_collection_payload(mood_id)}


@router.post("/{mood_id}/collection/stop")
def stop_collection(mood_id: str) -> dict:
    _require_mood(mood_id)
    session = mood_collection.stop(reason="user")
    counts = pds.dataset_counts(mood_registry.datasets_root(), mood_id)
    mood_registry.update_mood_ml(
        mood_id,
        status="untrained",
        burstCount=counts["burstCount"],
        frameCount=counts["frameCount"],
    )
    return {"session": session, **_collection_payload(mood_id)}


@router.get("/{mood_id}/collection/status")
def collection_status(mood_id: str) -> dict:
    _require_mood(mood_id)
    payload = _collection_payload(mood_id)
    session = payload.get("session")
    # Timer hit zero between polls: flip registry out of "collecting".
    if session is not None and not session.get("active"):
        mood = mood_registry.get_mood(mood_id)
        if mood is not None and mood.get("ml", {}).get("status") == "collecting":
            counts = payload.get("dataset", {})
            mood_registry.update_mood_ml(
                mood_id,
                status="untrained",
                burstCount=counts.get("burstCount", 0),
                frameCount=counts.get("frameCount", 0),
            )
    return payload


# --- burst review ----------------------------------------------------------------


@router.get("/{mood_id}/bursts")
def list_bursts(mood_id: str) -> dict:
    _require_mood(mood_id)
    bursts = pds.list_bursts(mood_registry.datasets_root(), mood_id)
    return {"bursts": bursts, **_collection_payload(mood_id)}


@router.get("/{mood_id}/bursts/{burst_id}/frames/{frame_name}")
def get_frame(mood_id: str, burst_id: str, frame_name: str) -> Response:
    try:
        path = pds.frame_path(
            mood_registry.datasets_root(), mood_id, burst_id, frame_name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Frame not found.")
    return Response(content=path.read_bytes(), media_type="image/jpeg")


@router.delete("/{mood_id}/bursts/{burst_id}")
def delete_burst(mood_id: str, burst_id: str) -> dict:
    _require_mood(mood_id)
    try:
        removed = pds.delete_burst(mood_registry.datasets_root(), mood_id, burst_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not removed:
        raise HTTPException(status_code=404, detail="Burst not found.")
    return {"deleted": burst_id, **_collection_payload(mood_id)}


@router.delete("/{mood_id}/bursts/{burst_id}/frames/{frame_name}")
def delete_frame(mood_id: str, burst_id: str, frame_name: str) -> dict:
    _require_mood(mood_id)
    try:
        removed = pds.delete_frame(
            mood_registry.datasets_root(), mood_id, burst_id, frame_name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not removed:
        raise HTTPException(status_code=404, detail="Frame not found.")
    return {"deleted": frame_name, **_collection_payload(mood_id)}


# --- training ----------------------------------------------------------------------


@router.post("/{mood_id}/train", status_code=202)
def train_mood(mood_id: str) -> dict:
    _require_mood(mood_id)
    if mood_collection.is_active():
        mood_collection.stop(reason="user")
    try:
        job = personal_training_jobs.start_job(
            mood_id,
            on_promoted=_hot_reload_engine,
        )
    except PersonalTrainingError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    mood_registry.update_mood_ml(mood_id, status="training")
    return {"job": job}


@training_router.get("/jobs/{job_id}")
def training_job(job_id: str) -> dict:
    job = personal_training_jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown training job: {job_id!r}")
    return {"job": job}


@training_router.get("/status")
def training_status() -> dict:
    return {"trainingActive": personal_training_jobs.is_running()}


@training_router.post("/consent")
def record_consent(payload: ConsentRequest) -> dict:
    doc = mood_registry.set_consent(payload.accepted)
    return {
        "consent": doc.get("consent", {"accepted": False}),
        "datasetFolder": str(mood_registry.datasets_root()),
    }
