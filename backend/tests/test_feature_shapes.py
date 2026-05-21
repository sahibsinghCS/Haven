"""Schema/shape consistency for burst-level feature fusion."""

from __future__ import annotations

import numpy as np

from roomos.features.burst import FrameBurst, FrameRecord
from roomos.features.fusion import FeatureFusion


PROMPTS = [
    "a person sitting at a desk",
    "a person sleeping in bed",
]
MOTION_GRID = 9


def _make_burst(n: int = 6) -> FrameBurst:
    frames = []
    for i in range(n):
        frames.append(
            FrameRecord(
                timestamp=float(i) * 0.25,
                frame_index=i,
                source="testvid.mp4",
                clip_embedding=np.random.RandomState(i).randn(32).astype(np.float32),
                clip_prompt_sim=np.random.RandomState(i + 10).rand(len(PROMPTS)).astype(np.float32),
                pose_landmarks=np.random.RandomState(i + 20).rand(33, 3).astype(np.float32),
                pose_visibility=np.random.RandomState(i + 30).rand(33).astype(np.float32),
                pose_present=1.0,
                pose_mean_visibility=0.7,
                pose_bbox=np.array([0.2, 0.1, 0.7, 0.95], dtype=np.float32),
                motion_mean=0.1 + 0.01 * i,
                motion_std=0.02,
                motion_max=0.3,
                motion_grid=np.random.RandomState(i + 40).rand(MOTION_GRID).astype(np.float32),
                posture={
                    "torso_angle": 0.1,
                    "body_height": 0.6,
                    "body_width": 0.2,
                    "height_to_width": 3.0,
                    "left_knee_angle": 2.7,
                    "right_knee_angle": 2.8,
                    "left_elbow_angle": 1.7,
                    "right_elbow_angle": 1.8,
                    "is_standing": 0.7,
                    "is_sitting": 0.2,
                    "is_lying": 0.1,
                    "center_x": 0.5,
                    "center_y": 0.5,
                },
            )
        )
    return FrameBurst(
        start_time=0.0,
        end_time=frames[-1].timestamp,
        source="testvid.mp4",
        frames=frames,
        burst_index=0,
    )


def test_fused_vector_matches_feature_names_length():
    fuse = FeatureFusion(prompt_labels=PROMPTS, motion_grid_size=MOTION_GRID)
    b = _make_burst()
    out = fuse.fuse(b)
    assert out.feature_vector.shape == (len(fuse.feature_names),)
    assert out.feature_vector.dtype == np.float32
    assert np.isfinite(out.feature_vector).all()
    assert out.metadata.get("burst_index") == 0


def test_disabling_groups_changes_schema():
    a = FeatureFusion(prompt_labels=PROMPTS, motion_grid_size=MOTION_GRID, use_pose=False, use_posture=False)
    b = FeatureFusion(prompt_labels=PROMPTS, motion_grid_size=MOTION_GRID)
    assert len(a.feature_names) < len(b.feature_names)


def test_zero_input_does_not_crash():
    fuse = FeatureFusion(prompt_labels=PROMPTS, motion_grid_size=MOTION_GRID)
    b = FrameBurst(
        start_time=0.0,
        end_time=1.0,
        source="empty",
        frames=[FrameRecord(timestamp=0.0, frame_index=0, source="empty")],
        burst_index=0,
    )
    out = fuse.fuse(b)
    assert out.feature_vector.shape == (len(fuse.feature_names),)
    assert np.isfinite(out.feature_vector).all()


def test_feature_names_deterministic():
    a = FeatureFusion(prompt_labels=PROMPTS, motion_grid_size=MOTION_GRID).feature_names
    b = FeatureFusion(prompt_labels=PROMPTS, motion_grid_size=MOTION_GRID).feature_names
    assert a == b
