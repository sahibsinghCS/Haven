import numpy as np

from roomos.video.frame_preprocess import strip_letterbox_pillarbox


def test_strip_letterbox_removes_black_bars():
    frame = np.zeros((100, 160, 3), dtype=np.uint8)
    frame[20:80, 30:130] = 180
    cropped = strip_letterbox_pillarbox(frame)
    assert cropped.shape[0] < 100
    assert cropped.shape[1] < 160
    assert cropped.mean() > 50
