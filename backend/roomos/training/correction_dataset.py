"""Build training rows from live feedback memory and corrected transitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pandas as pd

from ..dataset.schemas import FEATURE_META_COLUMNS
from ..utils.io import read_json
from ..utils.logging import get_logger

log = get_logger("roomos.training.correction_dataset")


def _features_dict_from_vector(
    vector: Sequence[float],
    feature_columns: Sequence[str],
) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for i, col in enumerate(feature_columns):
        try:
            out[col] = float(vector[i]) if i < len(vector) else 0.0
        except (TypeError, ValueError):
            out[col] = 0.0
    return out


def _row_from_features(
    *,
    source: str,
    label: str,
    features: Mapping[str, float],
    row_weight: float,
    burst_index: int,
    notes: str,
    dataset: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "source": source,
        "start_time": 0.0,
        "end_time": 0.0,
        "num_frames": 5,
        "burst_index": burst_index,
        "label": label,
        "row_weight": float(row_weight),
        "dataset": dataset,
        "notes": notes,
    }
    for k, v in features.items():
        row[k] = float(v)
    return row


def load_feedback_correction_rows(
    feedback_dir: Path,
    *,
    feature_columns: Sequence[str],
    row_weight: float,
    confirmation_row_weight: Optional[float] = None,
) -> List[dict[str, Any]]:
    path = feedback_dir / "feedback_examples.json"
    if not path.is_file():
        return []
    try:
        data = read_json(path)
    except Exception as e:
        log.warning("Could not read %s: %s", path, e)
        return []

    examples = data.get("examples", []) if isinstance(data, dict) else []
    cols = list(data.get("featureColumns") or feature_columns)
    if not cols:
        cols = list(feature_columns)

    rows: List[dict[str, Any]] = []
    for i, ex in enumerate(examples):
        if not isinstance(ex, dict):
            continue
        corrected = str(ex.get("corrected_label", "")).strip()
        if not corrected:
            continue
        vector = ex.get("vector") or []
        if not vector:
            feats = ex.get("features") or {}
            if isinstance(feats, dict):
                features = {k: float(v) for k, v in feats.items()}
            else:
                continue
        else:
            features = _features_dict_from_vector(vector, cols)

        predicted = str(ex.get("predicted_label", ""))
        eid = str(ex.get("id", i))
        if predicted == corrected:
            note = f"user_confirmed: {corrected}"
            dataset = "user_confirmation"
            w = float(confirmation_row_weight if confirmation_row_weight is not None else row_weight * 0.35)
        else:
            note = f"user_correction: {predicted} -> {corrected}"
            dataset = "user_correction"
            w = float(row_weight)
        rows.append(
            _row_from_features(
                source=f"feedback/{eid}",
                label=corrected,
                features=features,
                row_weight=w,
                burst_index=i,
                notes=note,
                dataset=dataset,
            )
        )
    return rows


def load_transition_correction_rows(
    transitions_dir: Path,
    *,
    row_weight: float,
) -> List[dict[str, Any]]:
    index_path = transitions_dir / "transitions_index.json"
    if not index_path.is_file():
        return []
    try:
        data = read_json(index_path)
    except Exception as e:
        log.warning("Could not read %s: %s", index_path, e)
        return []

    entries = data.get("transitions") or data.get("entries") or []
    if not isinstance(entries, list):
        entries = []
    rows: List[dict[str, Any]] = []
    for i, rec in enumerate(entries):
        if not isinstance(rec, dict):
            continue
        corrected = rec.get("corrected_label")
        if not corrected:
            continue
        feats = rec.get("features") or {}
        if not isinstance(feats, dict) or not feats:
            continue
        tid = str(rec.get("id", i))
        predicted = str(rec.get("to_label", ""))
        rows.append(
            _row_from_features(
                source=f"transition/{tid}",
                label=str(corrected),
                features={k: float(v) for k, v in feats.items()},
                row_weight=row_weight,
                burst_index=10_000 + i,
                notes=f"transition_relabel: {predicted} -> {corrected}",
                dataset="user_correction",
            )
        )
    return rows


def cap_correction_dataframe(
    df: pd.DataFrame,
    *,
    max_rows: int = 80,
) -> pd.DataFrame:
    """Keep the most recent corrections so retrain does not drown in duplicates."""
    if df.empty or len(df) <= max_rows:
        return df
    return df.tail(int(max_rows)).reset_index(drop=True)


def balance_correction_weight_in_merged(
    combined: pd.DataFrame,
    *,
    max_correction_weight_fraction: float = 0.12,
) -> pd.DataFrame:
    """Limit how much user rows can outweigh the multi-room base (prevents label whiplash)."""
    if combined.empty or "dataset" not in combined.columns or "row_weight" not in combined.columns:
        return combined
    out = combined.copy()
    is_corr = out["dataset"].astype(str).str.startswith("user_")
    base_mask = ~is_corr
    base_sum = float(out.loc[base_mask, "row_weight"].sum()) or 1.0
    corr_sum = float(out.loc[is_corr, "row_weight"].sum())
    cap = base_sum * float(max(0.01, min(0.5, max_correction_weight_fraction)))
    if corr_sum > cap and corr_sum > 0:
        scale = cap / corr_sum
        out.loc[is_corr, "row_weight"] = out.loc[is_corr, "row_weight"] * scale
        log.info(
            "Scaled correction row weights by %.3f (cap %.1f%% of base weight)",
            scale,
            max_correction_weight_fraction * 100,
        )
    return out


def build_correction_dataframe(
    *,
    feedback_dir: Path,
    transitions_dir: Path,
    feature_columns: Sequence[str],
    correction_row_weight: float = 1.0,
    confirmation_row_weight: Optional[float] = None,
    max_correction_rows: int = 80,
) -> pd.DataFrame:
    """All user-confirmed labels as feature rows (no duplicate merge)."""
    rows: List[dict[str, Any]] = []
    feedback_rows = load_feedback_correction_rows(
        feedback_dir,
        feature_columns=feature_columns,
        row_weight=correction_row_weight,
        confirmation_row_weight=confirmation_row_weight,
    )
    rows.extend(feedback_rows)
    # Transition API also writes to feedback_examples; skip duplicates by correction_id.
    feedback_ids = {
        str(r.get("source", "")).split("/", 1)[-1]
        for r in feedback_rows
        if str(r.get("source", "")).startswith("feedback/")
    }
    for tr in load_transition_correction_rows(
        transitions_dir,
        row_weight=correction_row_weight,
    ):
        tid = str(tr.get("source", "")).split("/", 1)[-1]
        rec_path = transitions_dir / "transitions_index.json"
        skip = False
        if rec_path.is_file():
            try:
                idx = read_json(rec_path)
                for rec in idx.get("transitions") or idx.get("entries") or []:
                    if str(rec.get("id")) == tid and str(rec.get("correction_id", "")) in feedback_ids:
                        skip = True
                        break
            except Exception:
                pass
        if not skip:
            rows.append(tr)
    if not rows:
        return pd.DataFrame()
    df = cap_correction_dataframe(pd.DataFrame(rows), max_rows=max_correction_rows)
    meta = set(FEATURE_META_COLUMNS) | {"label", "notes", "row_weight", "dataset"}
    for col in feature_columns:
        if col not in df.columns:
            df[col] = 0.0
    return df


def merge_base_and_corrections(
    base_df: pd.DataFrame,
    correction_df: pd.DataFrame,
    *,
    base_row_weight: float = 1.0,
    max_correction_weight_fraction: float = 0.12,
) -> pd.DataFrame:
    if base_df.empty and correction_df.empty:
        return pd.DataFrame()
    parts: List[pd.DataFrame] = []
    if not base_df.empty:
        b = base_df.copy()
        if "row_weight" not in b.columns:
            b["row_weight"] = float(base_row_weight)
        else:
            b["row_weight"] = b["row_weight"].fillna(float(base_row_weight))
        if "dataset" not in b.columns:
            b["dataset"] = "multi_room"
        parts.append(b)
    if not correction_df.empty:
        parts.append(correction_df)
    merged = pd.concat(parts, ignore_index=True)
    return balance_correction_weight_in_merged(
        merged,
        max_correction_weight_fraction=max_correction_weight_fraction,
    )
