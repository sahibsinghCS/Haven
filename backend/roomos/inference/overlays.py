"""Draw debug overlays onto a frame."""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np


_LABEL_COLORS = {
    "work": (245, 245, 245),
    "sleep": (180, 130, 90),
    "gaming": (250, 130, 200),
    "relaxing": (150, 220, 200),
    "away": (130, 130, 130),
    "unknown": (200, 200, 200),
}


def _color_for(label: str) -> tuple[int, int, int]:
    return _LABEL_COLORS.get(label, (200, 200, 200))


def draw_overlay(
    frame_bgr: np.ndarray,
    *,
    label: str,
    confidence: float,
    probs: Optional[Dict[str, float]] = None,
    status: str = "",
) -> np.ndarray:
    """Return a copy of the frame with the prediction overlaid."""
    import cv2

    img = frame_bgr.copy()
    h, w = img.shape[:2]

    # Top banner.
    banner_h = 70
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, banner_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)

    color = _color_for(label)
    cv2.putText(
        img,
        f"{label.upper()}  {confidence * 100:5.1f}%",
        (16, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        color,
        2,
        cv2.LINE_AA,
    )
    if status:
        cv2.putText(
            img,
            status,
            (16, 62),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (180, 180, 180),
            1,
            cv2.LINE_AA,
        )

    # Right-side per-class bars.
    if probs:
        bar_w = 180
        bar_h = 14
        gap = 6
        items = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
        x0 = w - bar_w - 16
        y = 16
        bg = img.copy()
        cv2.rectangle(
            bg,
            (x0 - 8, 8),
            (w - 8, 8 + (bar_h + gap) * len(items) + 8),
            (0, 0, 0),
            -1,
        )
        cv2.addWeighted(bg, 0.55, img, 0.45, 0, img)
        for cls, p in items:
            cls_color = _color_for(cls)
            fill = max(1, int(round(bar_w * float(p))))
            cv2.rectangle(img, (x0, y), (x0 + bar_w, y + bar_h), (60, 60, 60), -1)
            cv2.rectangle(img, (x0, y), (x0 + fill, y + bar_h), cls_color, -1)
            cv2.putText(
                img,
                f"{cls:>8} {float(p) * 100:4.1f}%",
                (x0 + 4, y + bar_h - 3),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (20, 20, 20),
                1,
                cv2.LINE_AA,
            )
            y += bar_h + gap

    return img
