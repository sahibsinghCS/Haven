"""Demo replay fixture loader and engine."""

from pathlib import Path

from roomos.demo.replay import DemoReplayFixture, render_demo_preview_frame


def test_fixture_loads():
    path = Path(__file__).resolve().parents[1] / "configs" / "demo_replay.json"
    fx = DemoReplayFixture.load(path)
    assert len(fx.steps) >= 4
    assert fx.loop is True
    assert fx.steps[0].state == "work"


def test_preview_frame_has_demo_label():
    frame = render_demo_preview_frame("work", step_index=0, sequence=1)
    assert frame.shape[0] > 0
    assert frame.shape[2] == 3
