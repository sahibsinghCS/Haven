"""MediaPipe Pose features.

We use MediaPipe's 33-landmark body model. If MediaPipe is not installed on
the host (which is common on bleeding-edge Python builds), the extractor
returns "no person detected" features so the pipeline keeps working.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..utils.logging import get_logger

log = get_logger("roomos.features.pose")

# MediaPipe Pose lists 33 landmarks.
NUM_LANDMARKS = 33

# A subset we trust enough to derive joint angles + posture from.
LANDMARK_NAMES = [
    "nose",
    "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear",
    "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "left_pinky", "right_pinky",
    "left_index", "right_index",
    "left_thumb", "right_thumb",
    "left_hip", "right_hip",
    "left_knee", "right_knee",
    "left_ankle", "right_ankle",
    "left_heel", "right_heel",
    "left_foot_index", "right_foot_index",
]
assert len(LANDMARK_NAMES) == NUM_LANDMARKS


@dataclass
class PoseFrameFeatures:
    person_present: bool
    landmarks: np.ndarray            # (33, 3) normalized x, y, z; zeros when absent
    visibility: np.ndarray           # (33,) per-landmark visibility 0..1
    mean_visibility: float
    bbox: np.ndarray                 # (4,) normalized xyxy of detected landmarks; zeros when absent


def _empty() -> PoseFrameFeatures:
    return PoseFrameFeatures(
        person_present=False,
        landmarks=np.zeros((NUM_LANDMARKS, 3), dtype=np.float32),
        visibility=np.zeros((NUM_LANDMARKS,), dtype=np.float32),
        mean_visibility=0.0,
        bbox=np.zeros((4,), dtype=np.float32),
    )


class PoseExtractor:
    def __init__(
        self,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        self.model_complexity = int(model_complexity)
        self.min_detection_confidence = float(min_detection_confidence)
        self.min_tracking_confidence = float(min_tracking_confidence)
        self._pose = None
        self._available: Optional[bool] = None

    def _probe(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import mediapipe as mp

            # MediaPipe >=0.10.30 ships the Tasks API only; RoomOS still uses the
            # classic ``mp.solutions.pose`` stack until we migrate.
            if not hasattr(mp, "solutions"):
                raise AttributeError(
                    "mediapipe is installed but legacy mp.solutions is missing "
                    "(Tasks-only build). Pin mediapipe<0.10.30 or disable pose in config."
                )
            self._available = True
        except Exception as e:
            log.warning(
                "MediaPipe pose unavailable (%s) — pose features will be zeroed out.",
                e,
            )
            self._available = False
        return self._available

    def load(self) -> None:
        if not self._probe():
            return
        if self._pose is not None:
            return
        try:
            import mediapipe as mp

            self._pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=self.model_complexity,
                enable_segmentation=False,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
            )
        except Exception as e:
            log.warning("MediaPipe Pose failed to load (%s); zeroing pose features.", e)
            self._available = False
            self._pose = None

    def close(self) -> None:
        if self._pose is not None:
            try:
                self._pose.close()
            except Exception:
                pass
            self._pose = None

    def __enter__(self) -> "PoseExtractor":
        self.load()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # --- extraction ----------------------------------------------------

    def extract(self, image_bgr: np.ndarray) -> PoseFrameFeatures:
        if not self._probe():
            return _empty()
        if self._pose is None:
            self.load()
        assert self._pose is not None

        # mediapipe wants RGB
        rgb = image_bgr[:, :, ::-1]
        result = self._pose.process(rgb)
        if not result.pose_landmarks:
            return _empty()

        lms = result.pose_landmarks.landmark
        arr = np.array(
            [[lm.x, lm.y, lm.z] for lm in lms],
            dtype=np.float32,
        )
        vis = np.array([lm.visibility for lm in lms], dtype=np.float32)

        visible = vis > 0.3
        if visible.any():
            x = arr[visible, 0]
            y = arr[visible, 1]
            bbox = np.array(
                [float(x.min()), float(y.min()), float(x.max()), float(y.max())],
                dtype=np.float32,
            )
        else:
            bbox = np.zeros((4,), dtype=np.float32)

        return PoseFrameFeatures(
            person_present=True,
            landmarks=arr,
            visibility=vis,
            mean_visibility=float(vis.mean()),
            bbox=bbox,
        )
