"""Tests for burst index selection (subsample collected frames)."""

from __future__ import annotations

from roomos.video.burst_sampling import burst_frame_indices, subsample_sequence


def test_burst_indices_full_span_when_n_equals_k():
    assert burst_frame_indices(5, 5) == [0, 1, 2, 3, 4]


def test_burst_indices_uniform_monotonic():
    idx = burst_frame_indices(20, 5, strategy="uniform")
    assert len(idx) == 5
    assert idx == sorted(idx)
    assert idx[0] == 0 and idx[-1] == 19


def test_burst_indices_endpoints_include_edges():
    idx = burst_frame_indices(20, 5, strategy="endpoints")
    assert idx[0] == 0 and idx[-1] == 19
    assert len(idx) == 5


def test_subsample_sequence_preserves_order():
    letters = list("abcdefghij")
    out = subsample_sequence(letters, 4, strategy="uniform")
    assert len(out) == 4
    assert out[0] == "a" and out[-1] == "j"


def test_small_n_returns_all_indices():
    assert burst_frame_indices(3, 10) == [0, 1, 2]
