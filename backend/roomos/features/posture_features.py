"""Geometric posture features derived from MediaPipe landmarks.

These are *interpretable* per-frame features that compress the 99-D landmark
array into a handful of body-shape descriptors that XGBoost can use directly.

All values are normalized (landmarks come back in [0,1] image coordinates
from MediaPipe), so they're scale-invariant w.r.t. frame resolution.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .pose_extractor import LANDMARK_NAMES, PoseFrameFeatures

# Pre-compute indices for the joints we care about so we don't pay dict-lookup
# cost per frame.
_IDX = {name: i for i, name in enumerate(LANDMARK_NAMES)}


@dataclass
class PostureFrameFeatures:
    person_present: bool
    # Body shape descriptors -------------------------------------------
    torso_angle: float          # angle of shoulders→hips line vs vertical (rad)
    body_height: float          # head-to-ankle vertical extent (normalized)
    body_width: float           # shoulder span (normalized)
    height_to_width: float
    # Joint angles -----------------------------------------------------
    left_knee_angle: float
    right_knee_angle: float
    left_elbow_angle: float
    right_elbow_angle: float
    # Coarse posture heuristics (one-hot-ish) --------------------------
    is_standing: float
    is_sitting: float
    is_lying: float
    # Position ---------------------------------------------------------
    center_x: float
    center_y: float


def _empty() -> PostureFrameFeatures:
    return PostureFrameFeatures(
        person_present=False,
        torso_angle=0.0,
        body_height=0.0,
        body_width=0.0,
        height_to_width=0.0,
        left_knee_angle=0.0,
        right_knee_angle=0.0,
        left_elbow_angle=0.0,
        right_elbow_angle=0.0,
        is_standing=0.0,
        is_sitting=0.0,
        is_lying=0.0,
        center_x=0.0,
        center_y=0.0,
    )


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Interior angle at ``b`` formed by points a-b-c (radians)."""
    ba = a - b
    bc = c - b
    nba = np.linalg.norm(ba)
    nbc = np.linalg.norm(bc)
    if nba < 1e-6 or nbc < 1e-6:
        return 0.0
    cos = float(np.dot(ba, bc) / (nba * nbc))
    cos = max(-1.0, min(1.0, cos))
    return float(np.arccos(cos))


def _midpoint(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a + b) * 0.5


class PostureExtractor:
    """Stateless converter: PoseFrameFeatures -> PostureFrameFeatures."""

    def extract(self, pose: PoseFrameFeatures) -> PostureFrameFeatures:
        if not pose.person_present:
            return _empty()

        lm = pose.landmarks[:, :2]  # only x, y (z is noisy)

        ls = lm[_IDX["left_shoulder"]]
        rs = lm[_IDX["right_shoulder"]]
        lh = lm[_IDX["left_hip"]]
        rh = lm[_IDX["right_hip"]]
        lk = lm[_IDX["left_knee"]]
        rk = lm[_IDX["right_knee"]]
        la = lm[_IDX["left_ankle"]]
        ra = lm[_IDX["right_ankle"]]
        le = lm[_IDX["left_elbow"]]
        re = lm[_IDX["right_elbow"]]
        lw = lm[_IDX["left_wrist"]]
        rw = lm[_IDX["right_wrist"]]
        nose = lm[_IDX["nose"]]

        shoulder_mid = _midpoint(ls, rs)
        hip_mid = _midpoint(lh, rh)
        ankle_mid = _midpoint(la, ra)

        torso_vec = hip_mid - shoulder_mid
        # Angle vs vertical (positive y in image space points DOWN).
        torso_angle = float(np.arctan2(abs(torso_vec[0]), abs(torso_vec[1]) + 1e-6))

        body_height = float(abs(nose[1] - ankle_mid[1]))
        body_width = float(np.linalg.norm(ls - rs))
        h_to_w = body_height / max(body_width, 1e-3)

        lk_angle = _angle(lh, lk, la)
        rk_angle = _angle(rh, rk, ra)
        le_angle = _angle(ls, le, lw)
        re_angle = _angle(rs, re, rw)

        # Heuristics — kept soft (continuous) so the classifier can override.
        # standing: torso ~vertical, h/w large, knees ~straight
        knee_avg = (lk_angle + rk_angle) * 0.5
        torso_horiz = float(min(1.0, torso_angle / (np.pi / 2.5)))
        h_to_w_norm = float(min(1.0, max(0.0, (h_to_w - 1.5) / 2.5)))
        knee_straight = float(min(1.0, max(0.0, (knee_avg - 2.0) / 1.0)))  # >2 rad = straight

        is_standing = (1.0 - torso_horiz) * h_to_w_norm * knee_straight
        is_sitting = (1.0 - torso_horiz) * (1.0 - knee_straight)
        is_lying = torso_horiz

        center_x = float(((ls[0] + rs[0] + lh[0] + rh[0]) / 4.0))
        center_y = float(((ls[1] + rs[1] + lh[1] + rh[1]) / 4.0))

        return PostureFrameFeatures(
            person_present=True,
            torso_angle=torso_angle,
            body_height=body_height,
            body_width=body_width,
            height_to_width=h_to_w,
            left_knee_angle=lk_angle,
            right_knee_angle=rk_angle,
            left_elbow_angle=le_angle,
            right_elbow_angle=re_angle,
            is_standing=is_standing,
            is_sitting=is_sitting,
            is_lying=is_lying,
            center_x=center_x,
            center_y=center_y,
        )
