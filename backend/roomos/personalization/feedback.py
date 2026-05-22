"""Online room-personalization from user corrections.

This is deliberately small and local-first: corrections become episodic
examples, and future predictions are gently biased toward nearby corrected
examples instead of retraining the base model on the live request path.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import numpy as np

from ..utils.io import append_jsonl, ensure_dir, read_json, write_json
from ..utils.logging import get_logger

log = get_logger("roomos.personalization.feedback")


@dataclass
class FeedbackCorrection:
    id: str
    created_at: str
    predicted_label: str
    corrected_label: str
    confidence: float
    notes: str
    screenshot_paths: List[str]
    influence: float
    nearest_similarity: float


class FeedbackReinforcementModel:
    """A persisted reward memory used to personalize probabilities.

    Each correction stores the feature vector from the 5-frame burst that the
    system just used, plus optional evidence screenshots. At inference time we
    find similar correction examples and add a bounded reward to their corrected
    label before re-normalizing probabilities.
    """

    def __init__(
        self,
        *,
        root_dir: str | Path,
        classes: Iterable[str],
        feature_columns: List[str],
        influence: float = 0.35,
        similarity_floor: float = 0.72,
        nearest_k: int = 8,
        max_examples: int = 500,
        penalty_factor: float = 0.45,
        personalization_blend: float = 1.0,
    ) -> None:
        self.root_dir = ensure_dir(root_dir)
        self.events_path = self.root_dir / "feedback_events.jsonl"
        self.examples_path = self.root_dir / "feedback_examples.json"
        self.screenshot_dir = ensure_dir(self.root_dir / "screenshots")
        self.classes = list(classes)
        self.feature_columns = list(feature_columns)
        self.influence = float(max(0.0, min(1.0, influence)))
        self.similarity_floor = float(max(0.0, min(0.99, similarity_floor)))
        self.nearest_k = max(1, int(nearest_k))
        self.max_examples = max(1, int(max_examples))
        self.penalty_factor = float(max(0.0, min(1.0, penalty_factor)))
        self.personalization_blend = float(max(0.0, min(1.0, personalization_blend)))
        self._lock = threading.RLock()
        self._examples: List[dict[str, Any]] = []
        self._load()

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._examples)

    def adjust_probabilities(
        self,
        features: Mapping[str, float],
        probabilities: Mapping[str, float],
    ) -> tuple[Dict[str, float], dict[str, Any]]:
        with self._lock:
            examples = list(self._examples)
        if not examples:
            return _normalize_probabilities(probabilities, self.classes), {
                "applied": False,
                "examples": 0,
                "memory_examples": 0,
                "nearest_similarity": 0.0,
            }

        x = self._vector(features)
        if not np.any(x):
            return _normalize_probabilities(probabilities, self.classes), {
                "applied": False,
                "examples": len(examples),
                "memory_examples": len(examples),
                "nearest_similarity": 0.0,
            }

        matches: List[tuple[float, dict[str, Any]]] = []
        for ex in examples:
            sim = _cosine_similarity(x, np.asarray(ex.get("vector", []), dtype=np.float32))
            if sim >= self.similarity_floor:
                matches.append((sim, ex))

        if not matches:
            nearest = max(
                (_cosine_similarity(x, np.asarray(ex.get("vector", []), dtype=np.float32)) for ex in examples),
                default=0.0,
            )
            return _normalize_probabilities(probabilities, self.classes), {
                "applied": False,
                "examples": len(examples),
                "memory_examples": len(examples),
                "nearest_similarity": float(nearest),
            }

        matches.sort(key=lambda item: item[0], reverse=True)
        matches = matches[: self.nearest_k]
        base = _normalize_probabilities(probabilities, self.classes)
        scores = dict(base)
        total_weight = 0.0

        for sim, ex in matches:
            corrected = str(ex.get("corrected_label", ""))
            predicted = str(ex.get("predicted_label", ""))
            if corrected not in scores:
                continue
            weight = ((sim - self.similarity_floor) / (1.0 - self.similarity_floor)) ** 2
            reward = self.influence * weight
            scores[corrected] = scores.get(corrected, 0.0) + reward
            if predicted in scores and predicted != corrected:
                scores[predicted] = max(
                    0.0, scores.get(predicted, 0.0) - reward * self.penalty_factor
                )
            total_weight += weight

        adjusted = _normalize_probabilities(scores, self.classes)
        if self.personalization_blend < 1.0:
            blended = {
                c: (1.0 - self.personalization_blend) * base.get(c, 0.0)
                + self.personalization_blend * adjusted.get(c, 0.0)
                for c in self.classes
            }
            adjusted = _normalize_probabilities(blended, self.classes)
        return adjusted, {
            "applied": total_weight > 0.0,
            "examples": len(examples),
            "memory_examples": len(examples),
            "matches": len(matches),
            "nearest_similarity": float(matches[0][0]),
            "influence": float(min(1.0, self.influence * total_weight)),
            "boosted_label": self._top_gain(base, adjusted),
        }

    def record_correction(
        self,
        *,
        predicted_label: str,
        corrected_label: str,
        confidence: float,
        features: Mapping[str, float],
        screenshots_bgr: Iterable[np.ndarray],
        notes: str = "",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> FeedbackCorrection:
        if corrected_label not in self.classes:
            raise ValueError(f"Unknown corrected label: {corrected_label!r}")

        now = datetime.now(timezone.utc).isoformat()
        correction_id = uuid.uuid4().hex
        event_dir = ensure_dir(self.screenshot_dir / correction_id)
        screenshot_paths = self._write_screenshots(event_dir, screenshots_bgr)
        vector = self._vector(features)

        example = {
            "id": correction_id,
            "created_at": now,
            "predicted_label": str(predicted_label),
            "corrected_label": str(corrected_label),
            "confidence": float(confidence),
            "notes": str(notes or ""),
            "vector": vector.tolist(),
            "screenshot_paths": screenshot_paths,
            "metadata": dict(metadata or {}),
        }

        with self._lock:
            self._examples.append(example)
            if len(self._examples) > self.max_examples:
                self._examples = self._examples[-self.max_examples :]
            self._persist_locked()

        append_jsonl(self.events_path, example)
        log.info(
            "Feedback memory: %d examples on disk at %s",
            len(self._examples),
            self.examples_path,
        )
        return FeedbackCorrection(
            id=correction_id,
            created_at=now,
            predicted_label=str(predicted_label),
            corrected_label=str(corrected_label),
            confidence=float(confidence),
            notes=str(notes or ""),
            screenshot_paths=screenshot_paths,
            influence=self.influence,
            nearest_similarity=1.0,
        )

    def _load(self) -> None:
        if not self.examples_path.exists():
            return
        try:
            data = read_json(self.examples_path)
            examples = data.get("examples", []) if isinstance(data, dict) else []
            if isinstance(examples, list):
                self._examples = examples[-self.max_examples :]
        except Exception as e:
            log.warning("Could not load feedback examples: %s", e)

    def status_payload(self) -> dict[str, Any]:
        with self._lock:
            examples = list(self._examples)
        last = examples[-1] if examples else None
        return {
            "memory_examples": len(examples),
            "similarity_floor": self.similarity_floor,
            "influence": self.influence,
            "personalization_blend": self.personalization_blend,
            "storage_dir": str(self.root_dir.resolve()),
            "examples_file": str(self.examples_path.resolve()),
            "events_log": str(self.events_path.resolve()),
            "screenshots_dir": str(self.screenshot_dir.resolve()),
            "last_correction": (
                {
                    "id": last.get("id"),
                    "at": last.get("created_at"),
                    "predicted_label": last.get("predicted_label"),
                    "corrected_label": last.get("corrected_label"),
                }
                if isinstance(last, dict)
                else None
            ),
        }

    @staticmethod
    def _top_gain(base: Mapping[str, float], adjusted: Mapping[str, float]) -> Optional[str]:
        best_label: Optional[str] = None
        best_delta = 0.0
        for cls in base:
            delta = float(adjusted.get(cls, 0.0)) - float(base.get(cls, 0.0))
            if delta > best_delta:
                best_delta = delta
                best_label = str(cls)
        return best_label if best_delta >= 0.02 else None

    def _persist_locked(self) -> None:
        write_json(
            self.examples_path,
            {
                "schemaVersion": 1,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "classes": self.classes,
                "featureColumns": self.feature_columns,
                "examples": self._examples,
            },
        )

    def _vector(self, features: Mapping[str, float]) -> np.ndarray:
        vals = []
        for col in self.feature_columns:
            try:
                vals.append(float(features.get(col, 0.0)))
            except (TypeError, ValueError):
                vals.append(0.0)
        arr = np.asarray(vals, dtype=np.float32)
        arr[~np.isfinite(arr)] = 0.0
        return arr

    def _write_screenshots(self, event_dir: Path, screenshots_bgr: Iterable[np.ndarray]) -> List[str]:
        out: List[str] = []
        try:
            import cv2
        except Exception as e:
            log.warning("OpenCV unavailable; skipping feedback screenshots: %s", e)
            return out

        for i, frame in enumerate(list(screenshots_bgr)[:5], start=1):
            if frame is None or not hasattr(frame, "shape"):
                continue
            path = event_dir / f"frame_{i:02d}.jpg"
            try:
                ok = cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 76])
                if ok:
                    out.append(str(path))
            except Exception as e:
                log.debug("Failed to write feedback screenshot %s: %s", path, e)
        return out


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape or not np.any(a) or not np.any(b):
        return 0.0
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-8:
        return 0.0
    return float(max(-1.0, min(1.0, np.dot(a, b) / denom)))


def _normalize_probabilities(
    probabilities: Mapping[str, float],
    classes: Iterable[str],
) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for cls in classes:
        try:
            out[cls] = max(0.0, float(probabilities.get(cls, 0.0)))
        except (TypeError, ValueError):
            out[cls] = 0.0
    total = sum(out.values())
    if total <= 1e-8:
        n = max(1, len(out))
        return {k: 1.0 / n for k in out}
    return {k: v / total for k, v in out.items()}
