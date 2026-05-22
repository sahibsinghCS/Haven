"""Deterministic demo replay — prerecorded snapshot sequence (not live camera)."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from ..inference.live_pipeline import LiveSnapshot

_UI_CLASSES: tuple[str, ...] = ("sleep", "gaming", "work", "relaxing", "away")
from ..utils.io import read_json
from ..utils.logging import get_logger

log = get_logger("roomos.demo.replay")

INFERENCE_SOURCE_LABEL = "Recorded demo sequence (not live camera)"
DATA_SOURCE = "demo-replay"


def _normalize_dist(raw: Dict[str, Any]) -> Dict[str, float]:
    vals = {c: float(raw.get(c, 0.0)) for c in _UI_CLASSES}
    total = sum(vals.values()) or 1.0
    return {c: vals[c] / total for c in _UI_CLASSES}


def _default_scene(state: str) -> Dict[str, object]:
    presets: Dict[str, Dict[str, object]] = {
        "work": {"lightColorHex": "#E8E4DC", "brightness": 78, "fanOn": False, "temperatureF": 70},
        "gaming": {"lightColorHex": "#6B4CFF", "brightness": 55, "fanOn": True, "temperatureF": 68},
        "sleep": {"lightColorHex": "#1A2030", "brightness": 8, "fanOn": False, "temperatureF": 66},
        "relaxing": {"lightColorHex": "#FFB86C", "brightness": 42, "fanOn": False, "temperatureF": 72},
        "away": {"lightColorHex": "#2A2A2A", "brightness": 12, "fanOn": False, "temperatureF": 65},
    }
    return dict(presets.get(state, presets["relaxing"]))


def render_demo_preview_frame(
    state: str,
    *,
    step_index: int,
    sequence: int,
    width: int = 640,
    height: int = 360,
) -> np.ndarray:
    """Synthetic preview frame — clearly labeled, not a live camera feed."""
    import cv2

    palette = {
        "work": (220, 200, 180),
        "gaming": (120, 80, 200),
        "sleep": (40, 45, 70),
        "relaxing": (100, 160, 255),
        "away": (50, 50, 55),
    }
    bg = palette.get(state, (60, 60, 60))
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = bg

    cv2.rectangle(frame, (0, 0), (width - 1, 44), (20, 20, 24), -1)
    cv2.putText(
        frame,
        "DEMO REPLAY — not live camera",
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (180, 255, 240),
        1,
        cv2.LINE_AA,
    )
    title = state.upper()
    cv2.putText(
        frame,
        title,
        (24, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.4,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    sub = f"step {step_index + 1} · burst {sequence}"
    cv2.putText(
        frame,
        sub,
        (24, height // 2 + 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (200, 200, 210),
        1,
        cv2.LINE_AA,
    )
    return frame


def encode_preview_jpeg(image_bgr: np.ndarray, quality: int = 72) -> bytes:
    import cv2

    ok, buf = cv2.imencode(".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Failed to encode demo preview JPEG")
    return buf.tobytes()


@dataclass
class DemoReplayStep:
    hold_sec: float
    state: str
    primary_confidence: float
    distribution: Dict[str, float]
    model_probs: Dict[str, float]
    rationale: List[str]
    applied_scene: Dict[str, object]
    personalization: Dict[str, object] = field(default_factory=dict)
    automation_mode: str = "dry_run"
    last_automation: Dict[str, object] = field(default_factory=dict)
    preview_image: Optional[str] = None


@dataclass
class DemoReplayFixture:
    version: int
    label: str
    loop: bool
    default_hold_sec: float
    steps: List[DemoReplayStep]

    @classmethod
    def load(cls, path: Path) -> "DemoReplayFixture":
        raw = read_json(path)
        steps_raw = raw.get("steps") or []
        default_hold = float(raw.get("default_hold_sec", 5.0))
        steps: List[DemoReplayStep] = []
        for item in steps_raw:
            state = str(item.get("state") or item.get("primary_state") or "relaxing")
            dist = _normalize_dist(item.get("distribution") or {state: 0.85})
            model = _normalize_dist(item.get("model_distribution") or item.get("model_probs") or dist)
            steps.append(
                DemoReplayStep(
                    hold_sec=float(item.get("hold_sec", default_hold)),
                    state=state,
                    primary_confidence=float(
                        item.get("primary_confidence", dist.get(state, 0.7))
                    ),
                    distribution=dist,
                    model_probs=model,
                    rationale=[str(x) for x in (item.get("rationale") or [])],
                    applied_scene=dict(
                        item.get("applied_scene") or _default_scene(state)
                    ),
                    personalization=dict(item.get("personalization") or {}),
                    automation_mode=str(item.get("automation_mode", "dry_run")),
                    last_automation=dict(item.get("last_automation") or {}),
                    preview_image=item.get("preview_image"),
                )
            )
        if not steps:
            raise ValueError(f"No steps in demo fixture: {path}")
        return cls(
            version=int(raw.get("version", 1)),
            label=str(raw.get("label", "Demo replay")),
            loop=bool(raw.get("loop", True)),
            default_hold_sec=default_hold,
            steps=steps,
        )


class DemoReplayEngine:
    """Background thread that replays fixture snapshots into SnapshotHub + preview."""

    def __init__(
        self,
        fixture: DemoReplayFixture,
        *,
        on_snapshot: Callable[[LiveSnapshot], None],
        on_preview_jpeg: Callable[[bytes], None],
        fixture_path: Optional[Path] = None,
        project_root: Optional[Path] = None,
    ) -> None:
        self._fixture = fixture
        self._on_snapshot = on_snapshot
        self._on_preview_jpeg = on_preview_jpeg
        self._fixture_path = fixture_path
        self._root = project_root or Path.cwd()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._seq = 0
        self._history: List[Dict[str, object]] = []
        self._step_index = 0

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start_background(self) -> None:
        if self.is_running():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="demo-replay", daemon=True)
        self._thread.start()
        log.info(
            "Demo replay started (%d steps, loop=%s, fixture=%s)",
            len(self._fixture.steps),
            self._fixture.loop,
            self._fixture_path or "inline",
        )

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None

    def _load_preview_bytes(self, step: DemoReplayStep, frame_bgr: np.ndarray) -> bytes:
        if step.preview_image:
            rel = Path(step.preview_image)
            path = rel if rel.is_absolute() else self._root / rel
            if path.exists():
                import cv2

                img = cv2.imread(str(path))
                if img is not None:
                    return encode_preview_jpeg(img)
        return encode_preview_jpeg(frame_bgr)

    def _emit_step(self, step: DemoReplayStep, step_index: int) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        self._seq += 1
        hist_entry: Dict[str, object] = {"t": now_iso}
        for c in _UI_CLASSES:
            hist_entry[c] = float(step.distribution.get(c, 0.0))
        self._history.append(hist_entry)
        if len(self._history) > 60:
            self._history = self._history[-60:]

        snap = LiveSnapshot(
            captured_at=now_iso,
            sequence=self._seq,
            primary_state=step.state,
            primary_confidence=step.primary_confidence,
            distribution=dict(step.distribution),
            model_probs=dict(step.model_probs),
            rationale=list(step.rationale),
            applied_scene=dict(step.applied_scene),
            confidence_history=list(self._history),
            personalization=dict(step.personalization),
            last_automation=dict(step.last_automation),
            automation_mode=step.automation_mode,
            data_source=DATA_SOURCE,
        )

        frame = render_demo_preview_frame(
            step.state,
            step_index=step_index,
            sequence=self._seq,
        )
        try:
            self._on_preview_jpeg(self._load_preview_bytes(step, frame))
        except Exception as e:
            log.warning("Demo preview encode failed: %s", e)

        try:
            self._on_snapshot(snap)
        except Exception as e:
            log.warning("Demo snapshot callback failed: %s", e)

    def _run(self) -> None:
        while not self._stop.is_set():
            for idx, step in enumerate(self._fixture.steps):
                if self._stop.is_set():
                    break
                self._step_index = idx
                self._emit_step(step, idx)
                deadline = time.monotonic() + max(0.5, step.hold_sec)
                while time.monotonic() < deadline:
                    if self._stop.wait(0.15):
                        return
            if not self._fixture.loop:
                break
        log.info("Demo replay stopped.")


def load_replay_engine(
    fixture_path: str | Path,
    *,
    on_snapshot: Callable[[LiveSnapshot], None],
    on_preview_jpeg: Callable[[bytes], None],
    project_root: Optional[Path] = None,
) -> DemoReplayEngine:
    path = Path(fixture_path)
    root = project_root or Path.cwd()
    resolved = path if path.is_absolute() else root / path
    fixture = DemoReplayFixture.load(resolved)
    return DemoReplayEngine(
        fixture,
        on_snapshot=on_snapshot,
        on_preview_jpeg=on_preview_jpeg,
        fixture_path=resolved,
        project_root=root,
    )
