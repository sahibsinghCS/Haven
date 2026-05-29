"""Persist and review state switches during live inference.

Each time the smoothed primary label changes, we save burst screenshots and
the fused feature vector so the user can later say "that was relaxing, not
sleep". Corrections feed the same :class:`FeedbackReinforcementModel` used by
"Teach the room" — future similar bursts get probability nudges automatically.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import numpy as np

from ..utils.io import append_jsonl, ensure_dir, read_json, write_json
from ..utils.logging import get_logger

log = get_logger("roomos.personalization.transitions")


@dataclass
class StateTransition:
    """One committed UI label change."""

    id: str
    captured_at: str
    from_label: str
    to_label: str
    confidence: float
    sequence: int
    screenshot_count: int
    corrected_label: Optional[str] = None
    correction_id: Optional[str] = None
    notes: str = ""

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "capturedAt": self.captured_at,
            "fromLabel": self.from_label,
            "toLabel": self.to_label,
            "confidence": float(self.confidence),
            "sequence": int(self.sequence),
            "screenshotCount": int(self.screenshot_count),
            "correctedLabel": self.corrected_label,
            "correctionId": self.correction_id,
            "notes": self.notes,
            "corrected": self.corrected_label is not None,
        }


class TransitionJournal:
    """Disk-backed log of label switches with frame evidence."""

    def __init__(
        self,
        *,
        root_dir: str | Path,
        max_entries: int = 200,
    ) -> None:
        self.root_dir = ensure_dir(root_dir)
        self.events_path = self.root_dir / "transitions.jsonl"
        self.index_path = self.root_dir / "transitions_index.json"
        self.screenshot_dir = ensure_dir(self.root_dir / "screenshots")
        self.max_entries = max(10, int(max_entries))
        self._lock = threading.RLock()
        self._entries: List[dict[str, Any]] = []
        self._load()

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._entries)

    def record_switch(
        self,
        *,
        from_label: str,
        to_label: str,
        confidence: float,
        sequence: int,
        features: Mapping[str, float],
        raw_probs: Mapping[str, float],
        screenshots_bgr: List[np.ndarray],
        rationale: Optional[List[str]] = None,
    ) -> StateTransition:
        """Append a transition and persist screenshots + features for relabeling."""
        tid = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        shot_dir = ensure_dir(self.screenshot_dir / tid)
        shot_paths = _write_screenshots(shot_dir, screenshots_bgr)

        record = {
            "id": tid,
            "captured_at": now,
            "from_label": str(from_label),
            "to_label": str(to_label),
            "confidence": float(confidence),
            "sequence": int(sequence),
            "screenshot_paths": shot_paths,
            "screenshot_count": len(shot_paths),
            "features": {k: float(v) for k, v in features.items()},
            "raw_probs": {k: float(v) for k, v in raw_probs.items()},
            "rationale": list(rationale or [])[:5],
            "corrected_label": None,
            "correction_id": None,
            "notes": "",
        }

        with self._lock:
            self._entries.append(record)
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries :]
            self._persist_index_locked()
        append_jsonl(self.events_path, record)
        log.info(
            "State transition %s: %s -> %s (%d frames)",
            tid[:8],
            from_label,
            to_label,
            len(shot_paths),
        )
        return StateTransition(
            id=tid,
            captured_at=now,
            from_label=str(from_label),
            to_label=str(to_label),
            confidence=float(confidence),
            sequence=int(sequence),
            screenshot_count=len(shot_paths),
        )

    def list_transitions(
        self,
        *,
        limit: int = 40,
        uncorrected_only: bool = False,
    ) -> List[StateTransition]:
        with self._lock:
            rows = list(reversed(self._entries))
        if uncorrected_only:
            rows = [r for r in rows if not r.get("corrected_label")]
        out: List[StateTransition] = []
        for r in rows[: max(1, limit)]:
            out.append(
                StateTransition(
                    id=str(r["id"]),
                    captured_at=str(r.get("captured_at", "")),
                    from_label=str(r.get("from_label", "")),
                    to_label=str(r.get("to_label", "")),
                    confidence=float(r.get("confidence", 0.0)),
                    sequence=int(r.get("sequence", 0)),
                    screenshot_count=int(r.get("screenshot_count", 0)),
                    corrected_label=r.get("corrected_label"),
                    correction_id=r.get("correction_id"),
                    notes=str(r.get("notes", "")),
                )
            )
        return out

    def get_record(self, transition_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            for r in self._entries:
                if str(r.get("id")) == transition_id:
                    return dict(r)
        return None

    def screenshot_path(self, transition_id: str, index: int) -> Optional[Path]:
        """1-based frame index like feedback screenshots."""
        rec = self.get_record(transition_id)
        if not rec:
            return None
        paths = rec.get("screenshot_paths") or []
        if index < 1 or index > len(paths):
            return None
        p = Path(str(paths[index - 1]))
        return p if p.is_file() else None

    def load_screenshots_bgr(self, transition_id: str) -> List[np.ndarray]:
        import cv2

        rec = self.get_record(transition_id)
        if not rec:
            return []
        out: List[np.ndarray] = []
        for rel in rec.get("screenshot_paths") or []:
            p = Path(str(rel))
            if not p.is_file():
                continue
            img = cv2.imread(str(p))
            if img is not None:
                out.append(img)
        return out

    def mark_corrected(
        self,
        transition_id: str,
        *,
        corrected_label: str,
        correction_id: str,
        notes: str = "",
    ) -> None:
        with self._lock:
            for r in self._entries:
                if str(r.get("id")) == transition_id:
                    r["corrected_label"] = str(corrected_label)
                    r["correction_id"] = str(correction_id)
                    r["notes"] = str(notes or "")
                    break
            self._persist_index_locked()

    def status_payload(self) -> dict[str, Any]:
        with self._lock:
            entries = list(self._entries)
        pending = sum(1 for e in entries if not e.get("corrected_label"))
        return {
            "enabled": True,
            "total": len(entries),
            "pendingReview": pending,
            "storageDir": str(self.root_dir.resolve()),
            "eventsLog": str(self.events_path.resolve()),
        }

    def _load(self) -> None:
        if self.index_path.exists():
            try:
                data = read_json(self.index_path)
                items = data.get("transitions", []) if isinstance(data, dict) else []
                if isinstance(items, list):
                    self._entries = items[-self.max_entries :]
                    return
            except Exception as e:
                log.warning("Could not load transitions index: %s", e)
        if not self.events_path.exists():
            return
        try:
            import json

            loaded: List[dict[str, Any]] = []
            with self.events_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        loaded.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            self._entries = loaded[-self.max_entries :]
            self._persist_index_locked()
        except Exception as e:
            log.warning("Could not rebuild transitions from jsonl: %s", e)

    def _persist_index_locked(self) -> None:
        write_json(
            self.index_path,
            {
                "schemaVersion": 1,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "transitions": self._entries,
            },
        )


def _write_screenshots(event_dir: Path, screenshots_bgr: List[np.ndarray]) -> List[str]:
    out: List[str] = []
    try:
        import cv2
    except Exception as e:
        log.warning("OpenCV unavailable; skipping transition screenshots: %s", e)
        return out

    for i, frame in enumerate(list(screenshots_bgr)[:5], start=1):
        if frame is None or not hasattr(frame, "shape"):
            continue
        path = event_dir / f"frame_{i:02d}.jpg"
        try:
            h, w = frame.shape[:2]
            if w > 480:
                scale = 480.0 / float(w)
                frame = cv2.resize(
                    frame,
                    (480, max(1, int(round(h * scale)))),
                    interpolation=cv2.INTER_AREA,
                )
            if cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80]):
                out.append(str(path))
        except Exception as e:
            log.debug("Failed to write transition screenshot %s: %s", path, e)
    return out
