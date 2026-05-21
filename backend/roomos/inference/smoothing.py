"""Temporal smoothing / hysteresis on burst-level class probabilities.

Each **burst** yields one probability vector from XGBoost. To avoid rapid
label flicker across successive bursts we apply, in order:

1. Exponential moving average over class probabilities (``ema_alpha``).
2. A minimum-confidence gate (below -> ``unknown``).
3. ``confirm_bursts`` consecutive agreeing burst predictions before switching.
4. A cooldown so the displayed label cannot change faster than ``cooldown_sec``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SmoothedPrediction:
    label: str
    confidence: float
    raw_probs: Dict[str, float]
    smoothed_probs: Dict[str, float]
    switched: bool


@dataclass
class PredictionSmoother:
    classes: List[str]
    unknown_label: str = "unknown"
    min_confidence: float = 0.45
    ema_alpha: float = 0.35
    confirm_bursts: int = 2
    cooldown_sec: float = 4.0

    _ema: Optional[Dict[str, float]] = field(default=None, init=False)
    _displayed_label: str = field(default="unknown", init=False)
    _pending_label: Optional[str] = field(default=None, init=False)
    _pending_count: int = field(default=0, init=False)
    _last_switch_at: Optional[float] = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._displayed_label = self.unknown_label

    def reset(self) -> None:
        self._ema = None
        self._displayed_label = self.unknown_label
        self._pending_label = None
        self._pending_count = 0
        self._last_switch_at = None

    def update(self, probs: Dict[str, float], now: Optional[float] = None) -> SmoothedPrediction:
        if now is None:
            now = time.monotonic()

        clean = {c: float(probs.get(c, 0.0)) for c in self.classes}
        total = sum(clean.values())
        if total > 0:
            clean = {c: v / total for c, v in clean.items()}

        if self._ema is None:
            self._ema = dict(clean)
        else:
            a = self.ema_alpha
            self._ema = {c: a * clean[c] + (1.0 - a) * self._ema[c] for c in self.classes}

        smoothed = self._ema
        top_label, top_conf = max(smoothed.items(), key=lambda kv: kv[1])

        proposed = top_label if top_conf >= self.min_confidence else self.unknown_label

        switched = False
        if proposed == self._displayed_label:
            self._pending_label = None
            self._pending_count = 0
        else:
            if proposed == self._pending_label:
                self._pending_count += 1
            else:
                self._pending_label = proposed
                self._pending_count = 1

            confirm_ok = self._pending_count >= max(1, self.confirm_bursts)
            cooldown_ok = (
                self._last_switch_at is None
                or (now - self._last_switch_at) >= self.cooldown_sec
            )
            if confirm_ok and cooldown_ok:
                self._displayed_label = proposed
                self._last_switch_at = now
                self._pending_label = None
                self._pending_count = 0
                switched = True

        return SmoothedPrediction(
            label=self._displayed_label,
            confidence=float(top_conf),
            raw_probs=clean,
            smoothed_probs=dict(smoothed),
            switched=switched,
        )


def smoothing_confirm_bursts(smoothing_cfg: object) -> int:
    """Read ``confirm_bursts`` from config, falling back to legacy ``confirm_windows``."""
    if smoothing_cfg is None:
        return 2
    if hasattr(smoothing_cfg, "get"):
        cb = smoothing_cfg.get("confirm_bursts")
        if cb is not None:
            return int(cb)
        return int(smoothing_cfg.get("confirm_windows", 2))
    raw = getattr(smoothing_cfg, "raw", None)
    if isinstance(raw, dict):
        if "confirm_bursts" in raw:
            return int(raw["confirm_bursts"])
        return int(raw.get("confirm_windows", 2))
    return 2
