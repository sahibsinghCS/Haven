from pathlib import Path

from roomos.training.correction_dataset import (
    build_correction_dataframe,
    merge_base_and_corrections,
)


def test_merge_correction_rows(tmp_path):
    base = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    # minimal inline rows
    import pandas as pd

    base_df = pd.DataFrame(
        [
            {
                "source": "img/a",
                "start_time": 0.0,
                "end_time": 1.0,
                "num_frames": 5,
                "burst_index": 0,
                "label": "work",
                "f1": 1.0,
                "row_weight": 1.0,
                "dataset": "multi_room",
            }
        ]
    )
    corr_df = pd.DataFrame(
        [
            {
                "source": "feedback/x",
                "start_time": 0.0,
                "end_time": 0.0,
                "num_frames": 5,
                "burst_index": 1,
                "label": "sleep",
                "f1": 2.0,
                "row_weight": 25.0,
                "dataset": "user_correction",
            }
        ]
    )
    merged = merge_base_and_corrections(base_df, corr_df, max_correction_weight_fraction=0.5)
    assert len(merged) == 2
    assert set(merged["label"]) == {"work", "sleep"}
    assert float(merged.loc[merged["label"] == "sleep", "row_weight"].iloc[0]) < 25.0
