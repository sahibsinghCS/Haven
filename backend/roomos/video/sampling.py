"""Small standalone helpers for frame-rate decisions.

We keep this separate from ``input.py`` so it can be unit-tested without
opening a real video device.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FrameSampler:
    """Returns True at most every ``period`` seconds of the input clock."""

    sample_fps: float
    _next_t: float = 0.0

    @property
    def period(self) -> float:
        return 1.0 / max(0.001, self.sample_fps)

    def should_emit(self, t: float) -> bool:
        if t >= self._next_t:
            self._next_t = t + self.period
            return True
        return False

    def reset(self) -> None:
        self._next_t = 0.0
