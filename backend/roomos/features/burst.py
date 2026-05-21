"""Burst aggregation: short multi-frame units for classification.

Each **burst** is one classification sample: we collect frames whose
timestamps fall in ``[burst_start, burst_start + duration_seconds]`` from the
sampled stream, then subsample to ``frame_count`` frames (``uniform`` or
``endpoints`` strategy). Live inference repeats this on a timer; offline video
is converted into overlapping or strided bursts.

This replaces dense sliding *windows* over long horizons with lightweight
bursts (default: 5 frames over ~2.5 s).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterator, List, Optional

import numpy as np

from ..video.burst_sampling import burst_frame_indices


@dataclass
class FrameRecord:
    """Per-frame features inside a burst (CLIP, pose, motion, posture)."""

    timestamp: float
    frame_index: int
    source: str
    clip_embedding: Optional[np.ndarray] = None
    clip_prompt_sim: Optional[np.ndarray] = None
    pose_landmarks: Optional[np.ndarray] = None
    pose_visibility: Optional[np.ndarray] = None
    pose_present: float = 0.0
    pose_mean_visibility: float = 0.0
    pose_bbox: Optional[np.ndarray] = None
    motion_mean: float = 0.0
    motion_std: float = 0.0
    motion_max: float = 0.0
    motion_grid: Optional[np.ndarray] = None
    posture: dict = field(default_factory=dict)
    # Live-only evidence image. Offline dataset extraction leaves this unset so
    # feature files do not accidentally retain camera frames.
    image_bgr: Optional[np.ndarray] = None


@dataclass
class FrameBurst:
    """One burst: ``frames`` are the subsampled classification unit (ordered)."""

    start_time: float
    end_time: float
    source: str
    frames: List[FrameRecord]
    burst_index: int = 0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def num_frames(self) -> int:
        return len(self.frames)


class BurstAggregator:
    """Collect sampled frames into time-bounded bursts, then subsample.

    Streaming API matches the old window aggregator: :meth:`push` one
    :class:`FrameRecord` at a time; receive zero or more completed
    :class:`FrameBurst` instances when a burst interval completes.

    Parameters
    ----------
    duration_seconds :
        Wall-clock span of each burst (stream time), e.g. 2.5.
    stride_seconds :
        Time between consecutive burst *starts* (overlap if stride < duration).
    frame_count :
        Target number of frames per burst after subsampling.
    sampling_strategy :
        ``uniform`` or ``endpoints`` — see :func:`roomos.video.burst_sampling.burst_frame_indices`.
    min_collected_frames :
        Minimum raw frames inside ``[start, start+duration]`` required before
        emitting (else burst is skipped). Typically ``frame_count`` or lower
        if the stream is sparse.
    """

    def __init__(
        self,
        duration_seconds: float = 2.5,
        stride_seconds: float = 1.5,
        frame_count: int = 5,
        sampling_strategy: str = "uniform",
        min_collected_frames: int = 4,
    ) -> None:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be > 0")
        if stride_seconds <= 0:
            raise ValueError("stride_seconds must be > 0")
        if frame_count < 1:
            raise ValueError("frame_count must be >= 1")

        self.duration_seconds = float(duration_seconds)
        self.stride_seconds = float(stride_seconds)
        self.frame_count = int(frame_count)
        self.sampling_strategy = str(sampling_strategy or "uniform")
        self.min_collected_frames = int(min_collected_frames)

        self._buf: Deque[FrameRecord] = deque()
        self._next_burst_start: Optional[float] = None
        self._burst_index = 0

    def reset(self) -> None:
        self._buf.clear()
        self._next_burst_start = None
        self._burst_index = 0

    def _trim_before(self, t: float) -> None:
        while self._buf and self._buf[0].timestamp < t:
            self._buf.popleft()

    def push(self, record: FrameRecord) -> List[FrameBurst]:
        if self._next_burst_start is None:
            self._next_burst_start = float(record.timestamp)

        self._buf.append(record)
        out: List[FrameBurst] = []

        # May emit multiple bursts if stream jumped or stride is very small.
        while self._next_burst_start is not None:
            s = self._next_burst_start
            e = s + self.duration_seconds
            if record.timestamp < e:
                break

            in_interval = [f for f in self._buf if s <= f.timestamp <= e]
            if len(in_interval) >= self.min_collected_frames:
                n = len(in_interval)
                k = min(self.frame_count, n)
                idx = burst_frame_indices(n, k, strategy=self.sampling_strategy)
                chosen = [in_interval[i] for i in idx]
                out.append(
                    FrameBurst(
                        start_time=float(chosen[0].timestamp),
                        end_time=float(chosen[-1].timestamp),
                        source=record.source,
                        frames=chosen,
                        burst_index=self._burst_index,
                    )
                )
                self._burst_index += 1

            self._next_burst_start = s + self.stride_seconds
            self._trim_before(self._next_burst_start)

        return out

    def flush(self) -> List[FrameBurst]:
        """Emit one final burst from trailing buffer (e.g. EOF on a file)."""
        if not self._buf or self._next_burst_start is None:
            return []
        frames = sorted(self._buf, key=lambda f: f.timestamp)
        self._buf.clear()
        if len(frames) < self.min_collected_frames:
            return []
        n = len(frames)
        k = min(self.frame_count, n)
        idx = burst_frame_indices(n, k, strategy=self.sampling_strategy)
        chosen = [frames[i] for i in idx]
        burst = FrameBurst(
            start_time=float(chosen[0].timestamp),
            end_time=float(chosen[-1].timestamp),
            source=chosen[-1].source,
            frames=chosen,
            burst_index=self._burst_index,
        )
        self._burst_index += 1
        self._next_burst_start = None
        return [burst]

    def feed(self, records: Iterator[FrameRecord]) -> Iterator[FrameBurst]:
        for r in records:
            for b in self.push(r):
                yield b
        for b in self.flush():
            yield b
