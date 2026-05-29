from roomos.inference.live_pipeline import _live_presence_fixup


def test_fixup_flips_away_when_work_close_and_motion():
    probs = {"work": 0.42, "gaming": 0.01, "sleep": 0.01, "relaxing": 0.0, "away": 0.56}
    feats = {"motion_mean_mean": 0.015}
    out = _live_presence_fixup(probs, feats)
    assert out["work"] > out["away"]
