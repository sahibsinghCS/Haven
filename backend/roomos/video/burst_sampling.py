"""Burst frame selection: pick ``k`` indices from ``n`` collected frames.

Used by :class:`roomos.features.burst.BurstAggregator` after collecting all
samples whose timestamps fall inside a burst interval
``[start, start + duration]``.
"""

from __future__ import annotations

from typing import List, Sequence, TypeVar

import numpy as np

T = TypeVar("T")


def burst_frame_indices(n: int, k: int, strategy: str = "uniform") -> List[int]:
    """Return ``k`` indices in ``[0, n-1]`` in ascending temporal order.

    Parameters
    ----------
    n :
        Number of collected frames in the burst interval.
    k :
        Target count (``burst.frame_count``).
    strategy :
        ``uniform`` — evenly spaced across the interval (default).
        ``endpoints`` — always includes first and last frame, then fills
        interior with even spacing (same as uniform when ``k >= 2`` and
        ``n > k``; differs mainly in intent / documentation).
    """
    if k <= 0 or n <= 0:
        return []
    if n <= k:
        return list(range(n))

    strategy = (strategy or "uniform").lower().strip()
    if strategy not in {"uniform", "endpoints"}:
        strategy = "uniform"

    if strategy == "endpoints" and k >= 2:
        idx = [0]
        if k > 2:
            raw = np.linspace(1, n - 2, k - 2) if n > 2 else np.zeros(k - 2)
            idx.extend(int(round(float(x))) for x in raw)
        idx.append(n - 1)
    else:
        raw = np.linspace(0, n - 1, k)
        idx = [int(round(float(x))) for x in raw]

    # Enforce strict increase (temporal order, no duplicate frames).
    for i in range(1, len(idx)):
        if idx[i] <= idx[i - 1]:
            idx[i] = min(idx[i - 1] + 1, n - 1)
    return idx


def subsample_sequence(items: Sequence[T], k: int, strategy: str = "uniform") -> List[T]:
    """Pick ``k`` elements from ``items`` preserving order."""
    n = len(items)
    if n == 0:
        return []
    idx = burst_frame_indices(n, k, strategy=strategy)
    return [items[i] for i in idx]
