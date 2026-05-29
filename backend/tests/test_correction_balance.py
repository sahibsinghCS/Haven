import pandas as pd

from roomos.training.correction_dataset import balance_correction_weight_in_merged


def test_correction_weight_capped_vs_base():
    base = pd.DataFrame(
        [{"label": "work", "row_weight": 1.0, "dataset": "multi_room", "f1": 1.0}]
    )
    corr = pd.DataFrame(
        [
            {
                "label": "work",
                "row_weight": 100.0,
                "dataset": "user_correction",
                "f1": 2.0,
            }
        ]
    )
    merged = pd.concat([base, corr], ignore_index=True)
    out = balance_correction_weight_in_merged(merged, max_correction_weight_fraction=0.10)
    corr_w = float(out.loc[out["dataset"] == "user_correction", "row_weight"].iloc[0])
    assert corr_w <= 0.11
