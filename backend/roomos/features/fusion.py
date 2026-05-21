"""Burst-level feature fusion.

Aggregates per-frame features inside a :class:`FrameBurst` into one tabular
row for XGBoost. Column layout is deterministic; training persists
``feature_columns.json`` for inference-time alignment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

import numpy as np

from .burst import FrameBurst, FrameRecord
from .posture_features import PostureFrameFeatures

POSTURE_FIELDS: tuple[str, ...] = (
    "torso_angle",
    "body_height",
    "body_width",
    "height_to_width",
    "left_knee_angle",
    "right_knee_angle",
    "left_elbow_angle",
    "right_elbow_angle",
    "is_standing",
    "is_sitting",
    "is_lying",
    "center_x",
    "center_y",
)

_CLIP_EMB_STATS = ("mean_norm", "std_norm", "drift")


@dataclass
class FusedBurst:
    """One training / inference row (one burst)."""

    feature_names: List[str]
    feature_vector: np.ndarray
    metadata: Dict[str, object]

    def as_dict(self) -> dict[str, float]:
        return {n: float(v) for n, v in zip(self.feature_names, self.feature_vector)}


def _safe_stats(prefix: str, arr: np.ndarray) -> Dict[str, float]:
    if arr.size == 0:
        return {
            f"{prefix}_mean": 0.0,
            f"{prefix}_std": 0.0,
            f"{prefix}_min": 0.0,
            f"{prefix}_max": 0.0,
            f"{prefix}_range": 0.0,
        }
    return {
        f"{prefix}_mean": float(arr.mean()),
        f"{prefix}_std": float(arr.std()),
        f"{prefix}_min": float(arr.min()),
        f"{prefix}_max": float(arr.max()),
        f"{prefix}_range": float(arr.max() - arr.min()),
    }


def _stat_names(prefix: str) -> list[str]:
    return [f"{prefix}_{s}" for s in ("mean", "std", "min", "max", "range")]


class FeatureFusion:
    """Stateless: ``FrameBurst`` -> one float vector."""

    def __init__(
        self,
        *,
        prompt_labels: Sequence[str],
        motion_grid_size: int = 16,
        use_clip: bool = True,
        use_pose: bool = True,
        use_motion: bool = True,
        use_posture: bool = True,
    ) -> None:
        self.prompt_labels = list(prompt_labels)
        self.motion_grid_size = int(motion_grid_size)
        self.use_clip = bool(use_clip)
        self.use_pose = bool(use_pose)
        self.use_motion = bool(use_motion)
        self.use_posture = bool(use_posture)
        self.feature_names: List[str] = self._build_feature_names()

    def _build_feature_names(self) -> List[str]:
        names: List[str] = ["meta_num_frames", "meta_duration_sec"]

        if self.use_clip:
            for prompt in self.prompt_labels:
                slug = _slugify_prompt(prompt)
                names.extend(_stat_names(f"clip_sim__{slug}"))
                names.append(f"clip_sim__{slug}_velocity")
            names.extend(_stat_names("clip_sim_top"))
            names.append("clip_sim_top_stability")
            for s in _CLIP_EMB_STATS:
                names.append(f"clip_emb_{s}")

        if self.use_pose:
            names.append("pose_present_ratio")
            names.append("pose_mean_visibility")
            names.append("pose_visibility_std")
            names.extend(["pose_bbox_w_mean", "pose_bbox_h_mean", "pose_bbox_area_mean"])
            names.append("pose_landmark_stability")

        if self.use_motion:
            names.extend(_stat_names("motion_mean"))
            names.extend(_stat_names("motion_max"))
            for i in range(self.motion_grid_size):
                names.append(f"motion_grid_{i:02d}_mean")
                names.append(f"motion_grid_{i:02d}_std")

        if self.use_posture:
            for f in POSTURE_FIELDS:
                names.extend(_stat_names(f"posture_{f}"))
            names.append("posture_standing_ratio")
            names.append("posture_sitting_ratio")
            names.append("posture_lying_ratio")

        return names

    def fuse(self, burst: FrameBurst) -> FusedBurst:
        feats: Dict[str, float] = {
            "meta_num_frames": float(burst.num_frames),
            "meta_duration_sec": float(burst.duration),
        }

        if self.use_clip:
            feats.update(self._fuse_clip(burst.frames))
        if self.use_pose:
            feats.update(self._fuse_pose(burst.frames))
        if self.use_motion:
            feats.update(self._fuse_motion(burst.frames))
        if self.use_posture:
            feats.update(self._fuse_posture(burst.frames))

        vec = np.array([feats.get(n, 0.0) for n in self.feature_names], dtype=np.float32)

        metadata = {
            "source": burst.source,
            "start_time": float(burst.start_time),
            "end_time": float(burst.end_time),
            "num_frames": int(burst.num_frames),
            "burst_index": int(burst.burst_index),
        }
        return FusedBurst(feature_names=self.feature_names, feature_vector=vec, metadata=metadata)

    def _fuse_clip(self, frames: List[FrameRecord]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        sims = [f.clip_prompt_sim for f in frames if f.clip_prompt_sim is not None and f.clip_prompt_sim.size]
        if not sims:
            for p in self.prompt_labels:
                slug = _slugify_prompt(p)
                out.update(_safe_stats(f"clip_sim__{slug}", np.zeros(0, dtype=np.float32)))
                out[f"clip_sim__{slug}_velocity"] = 0.0
            out.update(_safe_stats("clip_sim_top", np.zeros(0, dtype=np.float32)))
            out["clip_sim_top_stability"] = 0.0
            for s in _CLIP_EMB_STATS:
                out[f"clip_emb_{s}"] = 0.0
            return out

        stacked = np.stack(sims, axis=0)
        for j, p in enumerate(self.prompt_labels[: stacked.shape[1]]):
            slug = _slugify_prompt(p)
            col = stacked[:, j]
            out.update(_safe_stats(f"clip_sim__{slug}", col))
            out[f"clip_sim__{slug}_velocity"] = float(col[-1] - col[0])

        top_per_frame = stacked.max(axis=1)
        out.update(_safe_stats("clip_sim_top", top_per_frame))
        out["clip_sim_top_stability"] = float(top_per_frame.mean() - top_per_frame.std())

        embs = [f.clip_embedding for f in frames if f.clip_embedding is not None and f.clip_embedding.size]
        if embs:
            E = np.stack(embs, axis=0)
            norms = np.linalg.norm(E, axis=1)
            out["clip_emb_mean_norm"] = float(norms.mean())
            out["clip_emb_std_norm"] = float(norms.std())
            a = E[0] / (np.linalg.norm(E[0]) + 1e-8)
            b = E[-1] / (np.linalg.norm(E[-1]) + 1e-8)
            out["clip_emb_drift"] = float(1.0 - np.dot(a, b))
        else:
            out["clip_emb_mean_norm"] = 0.0
            out["clip_emb_std_norm"] = 0.0
            out["clip_emb_drift"] = 0.0

        return out

    def _fuse_pose(self, frames: List[FrameRecord]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        present = np.array([f.pose_present for f in frames], dtype=np.float32)
        out["pose_present_ratio"] = float(present.mean()) if present.size else 0.0

        vis_means = np.array([f.pose_mean_visibility for f in frames], dtype=np.float32)
        out["pose_mean_visibility"] = float(vis_means.mean()) if vis_means.size else 0.0
        out["pose_visibility_std"] = float(vis_means.std()) if vis_means.size else 0.0

        bboxes = [f.pose_bbox for f in frames if f.pose_bbox is not None]
        if bboxes:
            B = np.stack(bboxes, axis=0)
            w = np.clip(B[:, 2] - B[:, 0], 0.0, 1.0)
            h = np.clip(B[:, 3] - B[:, 1], 0.0, 1.0)
            a = w * h
            out["pose_bbox_w_mean"] = float(w.mean())
            out["pose_bbox_h_mean"] = float(h.mean())
            out["pose_bbox_area_mean"] = float(a.mean())
        else:
            out["pose_bbox_w_mean"] = 0.0
            out["pose_bbox_h_mean"] = 0.0
            out["pose_bbox_area_mean"] = 0.0

        lms = [f.pose_landmarks for f in frames if f.pose_landmarks is not None and f.pose_present > 0.5]
        if len(lms) >= 2:
            L = np.stack(lms, axis=0)
            per_joint_std = L[..., :2].std(axis=0)
            out["pose_landmark_stability"] = float(per_joint_std.mean())
        else:
            out["pose_landmark_stability"] = 0.0
        return out

    def _fuse_motion(self, frames: List[FrameRecord]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        mean_ts = np.array([f.motion_mean for f in frames], dtype=np.float32)
        max_ts = np.array([f.motion_max for f in frames], dtype=np.float32)
        out.update(_safe_stats("motion_mean", mean_ts))
        out.update(_safe_stats("motion_max", max_ts))

        grids = [f.motion_grid for f in frames if f.motion_grid is not None]
        if grids and len(grids[0]) == self.motion_grid_size:
            G = np.stack(grids, axis=0)
            for i in range(self.motion_grid_size):
                col = G[:, i]
                out[f"motion_grid_{i:02d}_mean"] = float(col.mean())
                out[f"motion_grid_{i:02d}_std"] = float(col.std())
        else:
            for i in range(self.motion_grid_size):
                out[f"motion_grid_{i:02d}_mean"] = 0.0
                out[f"motion_grid_{i:02d}_std"] = 0.0
        return out

    def _fuse_posture(self, frames: List[FrameRecord]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        present_frames = [f.posture for f in frames if f.posture]
        for field_name in POSTURE_FIELDS:
            col = np.array(
                [p.get(field_name, 0.0) for p in present_frames if field_name in p],
                dtype=np.float32,
            )
            out.update(_safe_stats(f"posture_{field_name}", col))

        if present_frames:
            n = float(len(present_frames))
            out["posture_standing_ratio"] = float(sum(p.get("is_standing", 0.0) for p in present_frames) / n)
            out["posture_sitting_ratio"] = float(sum(p.get("is_sitting", 0.0) for p in present_frames) / n)
            out["posture_lying_ratio"] = float(sum(p.get("is_lying", 0.0) for p in present_frames) / n)
        else:
            out["posture_standing_ratio"] = 0.0
            out["posture_sitting_ratio"] = 0.0
            out["posture_lying_ratio"] = 0.0
        return out


def _slugify_prompt(p: str) -> str:
    out = []
    for ch in p.lower().strip():
        if ch.isalnum():
            out.append(ch)
        elif ch in {" ", "-", "_"}:
            out.append("_")
    s = "".join(out).strip("_")
    while "__" in s:
        s = s.replace("__", "_")
    return s[:60] or "prompt"


def posture_features_to_dict(p: PostureFrameFeatures) -> dict[str, float]:
    if not p.person_present:
        return {}
    return {field_name: float(getattr(p, field_name)) for field_name in POSTURE_FIELDS}
