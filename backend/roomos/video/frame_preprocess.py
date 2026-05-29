"""Normalize webcam frames so preview and ML see the same picture as the camera app."""

from __future__ import annotations

import re
from typing import Optional, Tuple

import numpy as np

_ASPECT_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)$")


def parse_aspect_ratio(value: object) -> Optional[Tuple[float, float]]:
    if value is None or value == "" or value is False:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return float(value[0]), float(value[1])
    text = str(value).strip().lower()
    if text in ("none", "off", "false", "0"):
        return None
    m = _ASPECT_RE.match(text)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def strip_letterbox_pillarbox(
    frame: np.ndarray,
    *,
    threshold: int = 14,
    margin: int = 2,
    min_content_ratio: float = 0.55,
) -> np.ndarray:
    """Crop black bars often added by virtual webcam drivers (DroidCam, OBS, etc.)."""
    if frame is None or frame.size == 0:
        return frame
    try:
        import cv2
    except ImportError:
        return frame

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask = gray > int(threshold)
    if not np.any(mask):
        return frame

    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if len(rows) < 2 or len(cols) < 2:
        return frame

    y0, y1 = int(rows[0]), int(rows[-1]) + 1
    x0, x1 = int(cols[0]), int(cols[-1]) + 1
    h, w = frame.shape[:2]
    content_h = y1 - y0
    content_w = x1 - x0
    if content_h < h * min_content_ratio or content_w < w * min_content_ratio:
        return frame

    y0 = max(0, y0 - margin)
    x0 = max(0, x0 - margin)
    y1 = min(h, y1 + margin)
    x1 = min(w, x1 + margin)
    cropped = frame[y0:y1, x0:x1]
    return cropped if cropped.size else frame


def center_crop_aspect(
    frame: np.ndarray,
    aspect: Tuple[float, float],
) -> np.ndarray:
    """Center-crop to target aspect (e.g. 16:9) — matches many phone camera previews."""
    if frame is None or frame.size == 0:
        return frame
    aw, ah = aspect
    if aw <= 0 or ah <= 0:
        return frame
    target = aw / ah
    h, w = frame.shape[:2]
    current = w / float(h)
    if abs(current - target) < 0.02:
        return frame
    if current > target:
        new_w = max(1, int(round(h * target)))
        x0 = max(0, (w - new_w) // 2)
        return frame[:, x0 : x0 + new_w].copy()
    new_h = max(1, int(round(w / target)))
    y0 = max(0, (h - new_h) // 2)
    return frame[y0 : y0 + new_h, :].copy()


def preprocess_frame(
    frame: np.ndarray,
    cfg: Optional[dict] = None,
) -> np.ndarray:
    """Apply configured preprocessing before preview + burst sampling."""
    if frame is None or not isinstance(cfg, dict) or not cfg.get("enabled", True):
        return frame
    out = frame
    if bool(cfg.get("strip_letterbox", True)):
        out = strip_letterbox_pillarbox(
            out,
            threshold=int(cfg.get("letterbox_threshold", 14)),
            margin=int(cfg.get("letterbox_margin", 2)),
        )
    aspect = parse_aspect_ratio(cfg.get("aspect_ratio"))
    if aspect is not None:
        out = center_crop_aspect(out, aspect)
    return out
