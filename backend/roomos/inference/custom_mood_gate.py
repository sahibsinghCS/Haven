"""Guardrails so newly trained custom moods do not hijack live inference.

Custom classes are trained from a handful of bursts in one room. Even with
balanced class weights they can overfit background CLIP features and fire while
you are doing something else. This gate demotes a custom top label unless it
is confident, clearly ahead of builtins, and (when known) motion-plausible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, MutableMapping, Optional


@dataclass(frozen=True)
class CustomMoodGateConfig:
    enabled: bool = True
    min_confidence: float = 0.78
    min_margin: float = 0.18
    motion_feature: str = "motion_mean_mean"
    # Require at least this fraction of training-time median motion for the class.
    min_motion_fraction_of_median: float = 0.45
    # Customs trained with very low motion (reading at a desk) skip motion gating.
    low_motion_median_threshold: float = 0.038
    low_motion_min_confidence: float = 0.74
    low_motion_min_margin: float = 0.16


@dataclass(frozen=True)
class CustomMoodTrainStats:
    burst_count: int
    motion_median: float
    motion_p25: float


def build_custom_mood_gate_from_config(
    cfg: Mapping[str, object] | None,
) -> CustomMoodGateConfig:
    raw = dict(cfg or {})
    return CustomMoodGateConfig(
        enabled=bool(raw.get("enabled", True)),
        min_confidence=float(raw.get("min_confidence", 0.78)),
        min_margin=float(raw.get("min_margin", 0.18)),
        motion_feature=str(raw.get("motion_feature", "motion_mean_mean")),
        min_motion_fraction_of_median=float(
            raw.get("min_motion_fraction_of_median", 0.45)
        ),
        low_motion_median_threshold=float(
            raw.get("low_motion_median_threshold", 0.038)
        ),
        low_motion_min_confidence=float(raw.get("low_motion_min_confidence", 0.74)),
        low_motion_min_margin=float(raw.get("low_motion_min_margin", 0.16)),
    )


def apply_custom_mood_gate(
    probs: Mapping[str, float],
    features: Mapping[str, float],
    *,
    custom_mood_ids: set[str],
    train_stats: Mapping[str, CustomMoodTrainStats],
    cfg: CustomMoodGateConfig,
) -> Dict[str, float]:
    if not cfg.enabled or not custom_mood_ids:
        return {k: float(v) for k, v in probs.items()}

    out: Dict[str, float] = {k: max(0.0, float(v)) for k, v in probs.items()}
    if not out:
        return out

    top_label = max(out, key=out.get)
    if top_label not in custom_mood_ids:
        return _renormalize(out)

    top_p = float(out[top_label])
    builtin_best = max(
        (float(p) for label, p in out.items() if label not in custom_mood_ids),
        default=0.0,
    )
    margin = top_p - builtin_best

    motion = float(features.get(cfg.motion_feature, 0.0) or 0.0)
    stats = train_stats.get(top_label)
    low_motion_custom = (
        stats is not None
        and stats.motion_median < cfg.low_motion_median_threshold
    )
    motion_ok = True
    if stats is not None and stats.motion_median > 1e-6 and not low_motion_custom:
        motion_ok = motion >= stats.motion_median * cfg.min_motion_fraction_of_median

    min_conf = (
        cfg.low_motion_min_confidence if low_motion_custom else cfg.min_confidence
    )
    min_margin = cfg.low_motion_min_margin if low_motion_custom else cfg.min_margin

    if top_p >= min_conf and margin >= min_margin and motion_ok:
        return _renormalize(out)

    out[top_label] = 0.0
    return _renormalize(out)


def _renormalize(probs: MutableMapping[str, float]) -> Dict[str, float]:
    total = sum(max(0.0, float(v)) for v in probs.values())
    if total <= 1e-9:
        n = max(1, len(probs))
        return {k: 1.0 / n for k in probs}
    return {k: max(0.0, float(v)) / total for k, v in probs.items()}


def stats_from_json(raw: object) -> Dict[str, CustomMoodTrainStats]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, CustomMoodTrainStats] = {}
    for mood_id, payload in raw.items():
        if not isinstance(payload, dict):
            continue
        try:
            out[str(mood_id)] = CustomMoodTrainStats(
                burst_count=int(payload.get("burst_count", 0)),
                motion_median=float(payload.get("motion_median", 0.0)),
                motion_p25=float(payload.get("motion_p25", 0.0)),
            )
        except (TypeError, ValueError):
            continue
    return out
