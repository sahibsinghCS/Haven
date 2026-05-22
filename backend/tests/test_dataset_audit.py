"""Dataset audit helpers."""

from roomos.dataset.audit import (
    estimate_bursts_from_images,
    images_needed_for_bursts,
)


def test_burst_estimates():
    assert estimate_bursts_from_images(30, 5, 5) == 6
    assert estimate_bursts_from_images(55, 5, 5) == 11
    assert images_needed_for_bursts(12, 5, 5) == 60
