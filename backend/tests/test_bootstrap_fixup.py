from roomos.inference.live_pipeline import _bootstrap_live_fixup, _live_presence_fixup


def test_fixup_demotes_away_when_work_visible():
    probs = {"work": 0.29, "gaming": 0.02, "sleep": 0.02, "relaxing": 0.02, "away": 0.65}
    feats = {"motion_mean_mean": 0.02}
    out = _bootstrap_live_fixup(probs, feats)
    assert out["away"] < probs["away"]
    assert out["work"] > probs["work"]


def test_trained_model_fixup_same_scene():
    probs = {"work": 0.42, "gaming": 0.01, "sleep": 0.01, "relaxing": 0.0, "away": 0.56}
    feats = {"motion_mean_mean": 0.015}
    out = _live_presence_fixup(probs, feats)
    assert out["work"] > out["away"]
