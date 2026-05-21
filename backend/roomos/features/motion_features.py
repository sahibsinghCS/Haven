"""Lightweight motion features from consecutive frames.

We deliberately avoid optical flow here — it's expensive and not worth it for
coarse activity recognition. Instead:

* compute absolute frame-difference on grayscale, smoothed slightly;
* summarize into mean / std plus a small spatial grid of motion magnitudes
  (e.g. 4x4 cells) which gives the classifier some notion of *where* motion
  is happening (lower body / upper body / etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from ..utils.logging import get_logger

log = get_logger("roomos.features.motion")


@dataclass
class MotionFrameFeatures:
    motion_mean: float
    motion_std: float
    motion_max: float
    motion_grid: np.ndarray   # (rows*cols,) flattened mean magnitudes per cell


class MotionExtractor:
    def __init__(
        self,
        blur_ksize: int = 5,
        grid: Tuple[int, int] = (4, 4),
    ) -> None:
        self.blur_ksize = int(blur_ksize) if blur_ksize and blur_ksize >= 3 else 0
        self.grid_rows = int(grid[0])
        self.grid_cols = int(grid[1])
        self._prev_gray: Optional[np.ndarray] = None

    def reset(self) -> None:
        self._prev_gray = None

    def extract(self, image_bgr: np.ndarray) -> MotionFrameFeatures:
        import cv2

        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        if self.blur_ksize:
            gray = cv2.GaussianBlur(gray, (self.blur_ksize, self.blur_ksize), 0)

        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            self._prev_gray = gray
            grid_flat = np.zeros((self.grid_rows * self.grid_cols,), dtype=np.float32)
            return MotionFrameFeatures(
                motion_mean=0.0,
                motion_std=0.0,
                motion_max=0.0,
                motion_grid=grid_flat,
            )

        diff = cv2.absdiff(gray, self._prev_gray)
        self._prev_gray = gray

        # Normalize to roughly [0,1] (pixel diffs are 0..255).
        mag = diff.astype(np.float32) / 255.0

        # Spatial grid summary.
        h, w = mag.shape
        rows = max(1, self.grid_rows)
        cols = max(1, self.grid_cols)
        ys = np.linspace(0, h, rows + 1, dtype=int)
        xs = np.linspace(0, w, cols + 1, dtype=int)
        cells = np.zeros((rows, cols), dtype=np.float32)
        for ri in range(rows):
            for ci in range(cols):
                cell = mag[ys[ri]:ys[ri + 1], xs[ci]:xs[ci + 1]]
                if cell.size:
                    cells[ri, ci] = float(cell.mean())

        return MotionFrameFeatures(
            motion_mean=float(mag.mean()),
            motion_std=float(mag.std()),
            motion_max=float(mag.max()),
            motion_grid=cells.flatten().astype(np.float32),
        )
