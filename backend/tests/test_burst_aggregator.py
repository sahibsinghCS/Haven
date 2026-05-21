"""Tests for burst collection and emission."""

from __future__ import annotations

from roomos.features.burst import BurstAggregator, FrameRecord


def _rec(t: float, idx: int, source: str = "vid") -> FrameRecord:
    return FrameRecord(timestamp=t, frame_index=idx, source=source)


def test_burst_emits_after_duration_elapses():
    agg = BurstAggregator(
        duration_seconds=1.0,
        stride_seconds=10.0,
        frame_count=3,
        sampling_strategy="uniform",
        min_collected_frames=2,
    )
    out = []
    for i, t in enumerate([0.0, 0.25, 0.5, 0.75, 1.0]):
        out.extend(agg.push(_rec(t, i)))
    assert len(out) == 1
    b = out[0]
    assert b.num_frames == 3
    assert b.burst_index == 0


def test_min_collected_skips_sparse_burst():
    agg = BurstAggregator(
        duration_seconds=1.0,
        stride_seconds=1.0,
        frame_count=5,
        sampling_strategy="uniform",
        min_collected_frames=10,
    )
    seen = []
    for i, t in enumerate([0.0, 0.5, 1.0, 1.5, 2.0]):
        seen.extend(agg.push(_rec(t, i)))
    assert seen == []


def test_stride_allows_second_burst():
    agg = BurstAggregator(
        duration_seconds=1.0,
        stride_seconds=1.0,
        frame_count=2,
        sampling_strategy="uniform",
        min_collected_frames=3,
    )
    times = [0.0, 0.33, 0.66, 1.0, 1.33, 1.66, 2.0, 2.33, 2.66, 3.0]
    bursts = []
    for i, t in enumerate(times):
        bursts.extend(agg.push(_rec(t, i)))
    assert len(bursts) >= 2
    assert bursts[0].burst_index == 0
    assert bursts[1].burst_index == 1


def test_flush_emits_trailing_burst():
    agg = BurstAggregator(
        duration_seconds=10.0,
        stride_seconds=2.0,
        frame_count=3,
        sampling_strategy="uniform",
        min_collected_frames=3,
    )
    for i, t in enumerate([0.0, 0.5, 1.0]):
        agg.push(_rec(t, i))
    flushed = agg.flush()
    assert len(flushed) == 1
    assert flushed[0].num_frames == 3
