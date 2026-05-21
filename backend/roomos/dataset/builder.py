"""Dataset builder: video / stream -> one fused feature row per burst."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..config import Config
from ..features import (
    BurstAggregator,
    ClipExtractor,
    FeatureFusion,
    FrameRecord,
    FusedBurst,
    MotionExtractor,
    PoseExtractor,
    PostureExtractor,
)
from ..features.fusion import posture_features_to_dict
from ..utils.logging import get_logger
from ..video import open_video_source
from .schemas import FEATURE_META_COLUMNS, LabelSegment, label_for_burst

log = get_logger("roomos.dataset.builder")


@dataclass
class FeatureExtractionPipeline:
    """Perception models + burst-level fusion."""

    config: Config

    def __post_init__(self) -> None:
        f = self.config.features
        enabled = f.enabled

        self.use_clip = bool(enabled.get("clip", True))
        self.use_pose = bool(enabled.get("pose", True))
        self.use_motion = bool(enabled.get("motion", True))
        self.use_posture = bool(enabled.get("posture", True))

        prompts = list(f.clip.get("prompts", [])) if self.use_clip else []
        motion_grid = (
            tuple(f.motion.get("grid", [4, 4])) if self.use_motion else (0, 0)
        )

        self.prompt_labels = prompts
        self.motion_grid_size = int(motion_grid[0] * motion_grid[1])
        self.fusion = FeatureFusion(
            prompt_labels=self.prompt_labels,
            motion_grid_size=self.motion_grid_size,
            use_clip=self.use_clip,
            use_pose=self.use_pose,
            use_motion=self.use_motion,
            use_posture=self.use_posture,
        )

        self._clip: Optional[ClipExtractor] = None
        self._pose: Optional[PoseExtractor] = None
        self._motion: Optional[MotionExtractor] = None
        self._posture: Optional[PostureExtractor] = None

    def load(self) -> None:
        f = self.config.features
        if self.use_clip and self._clip is None:
            self._clip = ClipExtractor(
                model_name=f.clip.get("model_name", "ViT-B-32"),
                pretrained=f.clip.get("pretrained", "laion2b_s34b_b79k"),
                device=f.clip.get("device", "auto"),
                prompts=self.prompt_labels,
                keep_embedding=bool(f.clip.get("keep_embedding", True)),
            )
            self._clip.load()
        if self.use_pose and self._pose is None:
            self._pose = PoseExtractor(
                model_complexity=int(f.pose.get("model_complexity", 1)),
                min_detection_confidence=float(f.pose.get("min_detection_confidence", 0.5)),
                min_tracking_confidence=float(f.pose.get("min_tracking_confidence", 0.5)),
            )
            self._pose.load()
        if self.use_motion and self._motion is None:
            self._motion = MotionExtractor(
                blur_ksize=int(f.motion.get("diff_blur_ksize", 5)),
                grid=tuple(f.motion.get("grid", [4, 4])),
            )
        if self.use_posture and self._posture is None:
            self._posture = PostureExtractor()

    def reset_motion(self) -> None:
        """Clear motion state (call between bursts so diffs stay intra-burst)."""
        if self._motion is not None:
            self._motion.reset()

    def close(self) -> None:
        for x in (self._clip, self._pose):
            if x is not None:
                try:
                    x.close()
                except Exception:
                    pass
        self._clip = None
        self._pose = None
        self._motion = None
        self._posture = None

    def __enter__(self) -> "FeatureExtractionPipeline":
        self.load()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def frame_to_record(
        self, *, image_bgr: np.ndarray, frame_index: int, timestamp: float, source: str
    ) -> FrameRecord:
        rec = FrameRecord(timestamp=timestamp, frame_index=frame_index, source=source)

        if self.use_clip and self._clip is not None:
            cf = self._clip.extract(image_bgr)
            rec.clip_embedding = cf.embedding
            rec.clip_prompt_sim = cf.prompt_sim

        if self.use_pose and self._pose is not None:
            pf = self._pose.extract(image_bgr)
            rec.pose_landmarks = pf.landmarks
            rec.pose_visibility = pf.visibility
            rec.pose_present = 1.0 if pf.person_present else 0.0
            rec.pose_mean_visibility = pf.mean_visibility
            rec.pose_bbox = pf.bbox

            if self.use_posture and self._posture is not None:
                post = self._posture.extract(pf)
                rec.posture = posture_features_to_dict(post)
        elif self.use_posture and self._posture is not None:
            rec.posture = {}

        if self.use_motion and self._motion is not None:
            mf = self._motion.extract(image_bgr)
            rec.motion_mean = mf.motion_mean
            rec.motion_std = mf.motion_std
            rec.motion_max = mf.motion_max
            rec.motion_grid = mf.motion_grid

        return rec

    def run(
        self,
        source,
        *,
        sample_fps: Optional[float] = None,
        resize_width: Optional[int] = None,
        log_every: int = 0,
        source_id: Optional[str] = None,
    ) -> Iterator[FusedBurst]:
        """Yield fused rows for each completed burst from ``source``."""
        self.load()
        c = self.config
        b = c.burst
        sample_fps = sample_fps or float(c.video.sample_fps)
        resize_width = resize_width or int(c.video.resize_width)

        agg = BurstAggregator(
            duration_seconds=float(b.duration_seconds),
            stride_seconds=float(b.stride_seconds),
            frame_count=int(b.frame_count),
            sampling_strategy=str(b.sampling_strategy),
            min_collected_frames=int(b.min_collected_frames),
        )

        with open_video_source(
            source,
            sample_fps=sample_fps,
            resize_width=resize_width,
            read_timeout_sec=float(c.video.read_timeout_sec),
            log_every=log_every,
        ) as fs:
            sid = source_id if source_id is not None else str(source)
            self.reset_motion()
            for sf in fs:
                rec = self.frame_to_record(
                    image_bgr=sf.image,
                    frame_index=sf.index,
                    timestamp=sf.timestamp,
                    source=sid,
                )
                emitted = agg.push(rec)
                for burst in emitted:
                    yield self.fusion.fuse(burst)
                    self.reset_motion()
            for burst in agg.flush():
                yield self.fusion.fuse(burst)
                self.reset_motion()


def extract_bursts_from_video(
    config: Config,
    source,
    *,
    labels: Optional[Sequence[LabelSegment]] = None,
    source_id: Optional[str] = None,
    log_every: int = 0,
) -> pd.DataFrame:
    """Run perception on a video file and return one row per burst."""
    rows: List[dict] = []
    with FeatureExtractionPipeline(config) as pipe:
        sid = source_id if source_id is not None else str(source)
        for fb in pipe.run(source, source_id=sid, log_every=log_every):
            row = dict(fb.metadata)
            row.update(fb.as_dict())
            if labels:
                row["label"] = label_for_burst(
                    sid,
                    float(row["start_time"]),
                    float(row["end_time"]),
                    labels,
                )
            rows.append(row)
    if not rows:
        cols = list(FEATURE_META_COLUMNS) + list(pipe.fusion.feature_names)
        if labels:
            cols.append("label")
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows)


def save_features(df: pd.DataFrame, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() == ".csv":
        df.to_csv(p, index=False)
        return p
    if p.suffix.lower() in {".parquet", ".pq"}:
        try:
            df.to_parquet(p, index=False)
            return p
        except Exception as e:
            log.warning("parquet write failed (%s) — falling back to CSV", e)
            p = p.with_suffix(".csv")
            df.to_csv(p, index=False)
            return p
    try:
        out = p.with_suffix(".parquet")
        df.to_parquet(out, index=False)
        return out
    except Exception:
        out = p.with_suffix(".csv")
        df.to_csv(out, index=False)
        return out


def load_features(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if p.is_dir():
        frames: List[pd.DataFrame] = []
        for child in sorted(p.iterdir()):
            if child.suffix.lower() in {".parquet", ".pq"}:
                frames.append(pd.read_parquet(child))
            elif child.suffix.lower() == ".csv":
                frames.append(pd.read_csv(child))
        if not frames:
            raise FileNotFoundError(f"No feature files in {p}")
        return pd.concat(frames, ignore_index=True)
    if p.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(p)
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p)
    raise ValueError(f"Unsupported features path: {p}")


def merge_labels_into_features(
    df: pd.DataFrame,
    segments: Iterable[LabelSegment],
    min_overlap_ratio: float = 0.5,
) -> pd.DataFrame:
    segs = list(segments)
    if not segs:
        if "label" not in df.columns:
            df = df.copy()
            df["label"] = pd.NA
        return df

    labels = []
    for _, row in df.iterrows():
        labels.append(
            label_for_burst(
                source=str(row["source"]),
                start_time=float(row["start_time"]),
                end_time=float(row["end_time"]),
                segments=segs,
                min_overlap_ratio=min_overlap_ratio,
            )
        )
    out = df.copy()
    out["label"] = labels
    return out
