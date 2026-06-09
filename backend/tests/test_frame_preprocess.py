import numpy as np

from roomos.video.frame_preprocess import (
    flip_horizontal,
    preprocess_frame,
    strip_droidcam_watermark,
    strip_letterbox_pillarbox,
)


def test_strip_letterbox_removes_black_bars():
    frame = np.zeros((100, 160, 3), dtype=np.uint8)
    frame[20:80, 30:130] = 180
    cropped = strip_letterbox_pillarbox(frame)
    assert cropped.shape[0] < 100
    assert cropped.shape[1] < 160
    assert cropped.mean() > 50


def test_flip_horizontal_mirrors_columns():
    frame = np.zeros((4, 6, 3), dtype=np.uint8)
    frame[:, 0] = (255, 0, 0)
    flipped = flip_horizontal(frame)
    assert np.array_equal(flipped[:, -1], frame[:, 0])
    assert flipped[:, 0].mean() == 0


def test_strip_droidcam_watermark_fills_from_row_below():
    frame = np.full((120, 160, 3), 40, dtype=np.uint8)
    frame[0:18, 40:120] = (250, 250, 250)  # bright centered watermark text
    frame[18:30, :] = (55, 60, 65)
    cleaned = strip_droidcam_watermark(
        frame, height_ratio=0.12, min_band_px=18, sample_rows=8, blur_ksize=5
    )
    assert cleaned[0:18, 40:120].mean() < 90
    assert cleaned[60:80, :].mean() > 35


def test_preprocess_frame_flips_before_watermark_strip():
    frame = np.zeros((80, 100, 3), dtype=np.uint8)
    frame[0:10, 10:90] = 255
    out = preprocess_frame(
        frame,
        {
            "enabled": True,
            "strip_letterbox": False,
            "strip_droidcam_watermark": True,
            "flip_horizontal": True,
            "droidcam_watermark_height_ratio": 0.12,
            "droidcam_watermark_blur_ksize": 11,
        },
    )
    assert out.shape == frame.shape
    assert out[0:10, :].mean() < 200
