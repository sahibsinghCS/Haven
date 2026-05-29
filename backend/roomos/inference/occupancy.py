"""Inference-time occupancy gate (cheap "is anyone in the room?" check).

Bootstrap / small personal models trained on synthetic stills frequently
mis-classify an empty couch, bed, or desk as ``work`` / ``relaxing`` /
``sleep`` — the XGBoost head has only ever seen *positive* examples of those
classes and never learned a strong "no person => away" prior.

This module adds a tiny inference-time gate that runs *after* the XGBoost
prediction and *before* feedback personalization / smoothing. It consults
features that are already in the fused burst row, so it costs nothing extra:

* ``clip_sim__a_person_*_mean`` — max similarity to any "a person ..." prompt
* ``clip_sim__an_empty_room_with_no_people_mean`` — explicit empty-room prompt
* ``motion_mean_mean`` — burst-average frame-diff motion
* ``pose_present_ratio`` — only when MediaPipe pose is enabled

If the gate decides the scene is **empty**, we force a floor of probability
mass on the configured ``away_label``. The smoother and personalization layers
still run normally on top, so user corrections continue to work.

Design notes
------------
* We deliberately use a **margin** (empty - person) on CLIP similarity, not
  absolute thresholds. CLIP cosine similarities are model-dependent (ViT-B-32
  laion2b values cluster around 0.18–0.28 for matching prompts), so an
  absolute cutoff would be brittle across CLIP backbones.
* We require a low-motion check too, so a person walking through frame
  (high motion + brief empty CLIP match) does not flip the room to ``away``.
* When the MediaPipe pose feature group is enabled, ``pose_present_ratio`` is
  the most reliable presence signal and takes priority.
* The module has zero external dependencies beyond ``numpy`` so it stays cheap
  on the live request path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence


# Default CLIP prompts must match the slugs produced by
# ``roomos.features.fusion._slugify_prompt`` for the prompts shipped in
# ``configs/default.yaml``. Keeping the literal strings here means the gate
# stays correct even if someone deletes ``default.yaml`` after training.
_DEFAULT_PERSON_PROMPTS: tuple[str, ...] = (
    "a person sitting at a desk working on a computer",
    "a person typing at a laptop",
    "a person lying in bed sleeping",
    "a person playing video games with a controller",
    "a person watching television and relaxing",
    "a person relaxing while lying on a bed awake",
    "a person reading a book in bed",
    "a person scrolling on a phone while lying in bed",
    "a person reading a book on a couch",
    "a person eating a meal",
    "a person exercising or stretching",
)

_DEFAULT_EMPTY_PROMPTS: tuple[str, ...] = (
    "an empty room with no people",
)

# Scene prompts from ``default.yaml`` — empty couch/desk/bed without a person.
# Using only the generic empty-room prompt misses many false ``work`` / ``relaxing``
# calls on furniture-only frames.
_DEFAULT_SCENE_EMPTY_PROMPTS: tuple[str, ...] = (
    "an empty bedroom with a made bed",
    "an unoccupied office desk with a monitor and keyboard",
    "an empty living room couch",
)

# Labels the XGBoost head over-predicts when no one is in frame.
_ACTIVITY_LABELS: tuple[str, ...] = ("work", "relaxing", "sleep", "gaming")


def _slugify_prompt(p: str) -> str:
    """Mirror of ``roomos.features.fusion._slugify_prompt`` (duplicated to keep
    this module dependency-free)."""
    out: list[str] = []
    for ch in p.lower().strip():
        if ch.isalnum():
            out.append(ch)
        elif ch in {" ", "-", "_"}:
            out.append("_")
    s = "".join(out).strip("_")
    while "__" in s:
        s = s.replace("__", "_")
    return s[:60] or "prompt"


@dataclass
class OccupancyDecision:
    """Result of one occupancy check on a fused burst."""

    empty: bool
    person_score: float
    empty_score: float
    motion: float
    pose_present_ratio: Optional[float]
    reason: str  # person_visible | no_signal | empty_clip | empty_pose | empty_scene | soft_empty
    soft_empty: bool = False  # weak person CLIP — cap work/relaxing without full away floor

    def to_dict(self) -> dict:
        return {
            "empty": bool(self.empty),
            "person_score": float(self.person_score),
            "empty_score": float(self.empty_score),
            "motion": float(self.motion),
            "pose_present_ratio": (
                None
                if self.pose_present_ratio is None
                else float(self.pose_present_ratio)
            ),
            "reason": str(self.reason),
            "soft_empty": bool(self.soft_empty),
        }


@dataclass
class OccupancyGate:
    """Cheap CLIP+motion(+pose) gate that vetoes activity labels on empty scenes.

    Construct once at engine start and call :meth:`detect` per burst.

    Knobs (all overridable from ``inference.yaml`` → ``inference.occupancy``):

    ``enabled``
        Master switch.
    ``empty_margin``
        Minimum ``empty_score - person_score`` to consider the CLIP signal
        "empty-wins". 0.015 is conservative for ViT-B-32 / laion2b.
    ``motion_max_for_empty``
        Burst-average ``motion_mean_mean`` must be below this for CLIP-based
        empty detection (avoids flipping during walk-through).
    ``pose_present_floor``
        When pose features are enabled, treat the frame as unoccupied if
        ``pose_present_ratio`` is below this.
    ``away_floor_prob``
        When the gate fires, force the configured ``away_label`` to at least
        this probability (then renormalize). 0.75 is firm enough for the
        smoother to settle on ``away`` but soft enough that personalization
        can still nudge.
    """

    away_label: str = "away"
    unknown_label: str = "unknown"
    person_prompts: Sequence[str] = field(
        default_factory=lambda: list(_DEFAULT_PERSON_PROMPTS)
    )
    empty_prompts: Sequence[str] = field(
        default_factory=lambda: list(_DEFAULT_EMPTY_PROMPTS)
    )
    scene_empty_prompts: Sequence[str] = field(
        default_factory=lambda: list(_DEFAULT_SCENE_EMPTY_PROMPTS)
    )
    empty_margin: float = 0.015
    scene_empty_margin: float = 0.008
    motion_max_for_empty: float = 0.02
    motion_min_for_person: float = 0.012
    pose_present_floor: float = 0.2
    away_floor_prob: float = 0.75
    soft_empty_away_floor_prob: float = 0.55
    person_absence_clip_max: float = 0.24
    activity_prob_cap: float = 0.14
    enabled: bool = True
    pose_enabled: bool = False

    _person_keys: List[str] = field(init=False, default_factory=list)
    _empty_keys: List[str] = field(init=False, default_factory=list)
    _scene_empty_keys: List[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self._person_keys = [
            f"clip_sim__{_slugify_prompt(p)}_mean" for p in self.person_prompts
        ]
        self._empty_keys = [
            f"clip_sim__{_slugify_prompt(p)}_mean" for p in self.empty_prompts
        ]
        self._scene_empty_keys = [
            f"clip_sim__{_slugify_prompt(p)}_mean" for p in self.scene_empty_prompts
        ]

    # ------------------------------------------------------------------

    def detect(self, features: Mapping[str, float]) -> OccupancyDecision:
        person_score = 0.0
        person_seen = False
        for key in self._person_keys:
            if key in features:
                person_seen = True
                v = float(features.get(key, 0.0) or 0.0)
                if v > person_score:
                    person_score = v

        empty_score = 0.0
        empty_seen = False
        for key in self._empty_keys:
            if key in features:
                empty_seen = True
                v = float(features.get(key, 0.0) or 0.0)
                if v > empty_score:
                    empty_score = v

        scene_empty_score = 0.0
        scene_seen = False
        for key in self._scene_empty_keys:
            if key in features:
                scene_seen = True
                v = float(features.get(key, 0.0) or 0.0)
                if v > scene_empty_score:
                    scene_empty_score = v
        combined_empty = max(empty_score, scene_empty_score)
        if scene_seen or empty_seen:
            empty_seen = True
            empty_score = combined_empty

        motion = float(features.get("motion_mean_mean", 0.0) or 0.0)

        pose_val: Optional[float] = None
        if self.pose_enabled:
            pose_val = float(features.get("pose_present_ratio", 0.0) or 0.0)

        # Live webcam: movement in frame → someone is here (fixes false Away on DroidCam).
        if motion >= self.motion_min_for_person:
            return OccupancyDecision(
                empty=False,
                person_score=person_score,
                empty_score=empty_score,
                motion=motion,
                pose_present_ratio=pose_val,
                reason="motion_present",
            )

        if not self.enabled:
            return OccupancyDecision(
                empty=False,
                person_score=person_score,
                empty_score=empty_score,
                motion=motion,
                pose_present_ratio=pose_val,
                reason="disabled",
            )

        # Pose is the strongest signal when available.
        if (
            pose_val is not None
            and pose_val < self.pose_present_floor
            and motion <= self.motion_max_for_empty * 2.0
        ):
            return OccupancyDecision(
                empty=True,
                person_score=person_score,
                empty_score=empty_score,
                motion=motion,
                pose_present_ratio=pose_val,
                reason="empty_pose",
            )

        # CLIP-based fallback (used when pose is disabled or pose ambiguous).
        if empty_seen and person_seen:
            margin = empty_score - person_score
            scene_margin = scene_empty_score - person_score
            if motion <= self.motion_max_for_empty:
                if margin >= self.empty_margin:
                    return OccupancyDecision(
                        empty=True,
                        person_score=person_score,
                        empty_score=empty_score,
                        motion=motion,
                        pose_present_ratio=pose_val,
                        reason="empty_clip",
                    )
                if scene_margin >= self.scene_empty_margin:
                    return OccupancyDecision(
                        empty=True,
                        person_score=person_score,
                        empty_score=empty_score,
                        motion=motion,
                        pose_present_ratio=pose_val,
                        reason="empty_scene",
                    )
                # Furniture-only frame: person CLIP is weak but couch/desk empty prompts win.
                if (
                    person_score <= self.person_absence_clip_max
                    and scene_empty_score >= person_score
                    and scene_margin >= 0.0
                ):
                    return OccupancyDecision(
                        empty=True,
                        person_score=person_score,
                        empty_score=empty_score,
                        motion=motion,
                        pose_present_ratio=pose_val,
                        reason="empty_scene",
                    )

        # Soft empty: person signal too weak to trust work/relaxing; cap activity probs.
        if (
            person_seen
            and empty_seen
            and person_score <= self.person_absence_clip_max
            and empty_score > person_score
            and motion <= self.motion_max_for_empty * 1.5
        ):
            return OccupancyDecision(
                empty=False,
                soft_empty=True,
                person_score=person_score,
                empty_score=empty_score,
                motion=motion,
                pose_present_ratio=pose_val,
                reason="soft_empty",
            )

        if not person_seen and not empty_seen and pose_val is None:
            return OccupancyDecision(
                empty=False,
                person_score=person_score,
                empty_score=empty_score,
                motion=motion,
                pose_present_ratio=pose_val,
                reason="no_signal",
            )

        return OccupancyDecision(
            empty=False,
            person_score=person_score,
            empty_score=empty_score,
            motion=motion,
            pose_present_ratio=pose_val,
            reason="person_visible",
        )

    # ------------------------------------------------------------------

    def apply(
        self,
        probs: Mapping[str, float],
        decision: OccupancyDecision,
    ) -> Dict[str, float]:
        """Return possibly-overridden probabilities for an empty scene.

        On non-empty decisions this is a no-op (returns a fresh dict copy).
        On empty decisions we lift ``away_label`` to at least
        ``away_floor_prob`` and proportionally shrink the other classes, then
        renormalize.
        """
        adjusted: Dict[str, float] = {
            k: max(0.0, float(v)) for k, v in probs.items()
        }
        if not self.enabled:
            return adjusted

        if decision.soft_empty and not decision.empty:
            if self.away_label in adjusted:
                floor = max(0.0, min(1.0, float(self.soft_empty_away_floor_prob)))
                current_away = float(adjusted.get(self.away_label, 0.0))
                if current_away < floor:
                    others = [k for k in adjusted if k != self.away_label]
                    others_sum = sum(adjusted[k] for k in others)
                    remaining = max(0.0, 1.0 - floor)
                    if others_sum > 1e-9 and remaining > 0.0:
                        scale = remaining / others_sum
                        for k in others:
                            adjusted[k] *= scale
                    adjusted[self.away_label] = floor
            adjusted = self._cap_activity_probs(adjusted)
            total = sum(adjusted.values()) or 1.0
            adjusted = {k: v / total for k, v in adjusted.items()}
            adjusted = self._cap_activity_probs(adjusted)
            total = sum(adjusted.values()) or 1.0
            return {k: v / total for k, v in adjusted.items()}

        if not decision.empty:
            return adjusted
        if self.away_label not in adjusted:
            adjusted[self.away_label] = 0.0

        adjusted = self._cap_activity_probs(adjusted)
        floor = max(0.0, min(1.0, float(self.away_floor_prob)))
        current_away = float(adjusted.get(self.away_label, 0.0))
        if current_away >= floor:
            total = sum(adjusted.values()) or 1.0
            return {k: v / total for k, v in adjusted.items()}

        others = [k for k in adjusted if k != self.away_label]
        others_sum = sum(adjusted[k] for k in others)
        remaining = max(0.0, 1.0 - floor)
        if others_sum > 1e-9 and remaining > 0.0:
            scale = remaining / others_sum
            for k in others:
                adjusted[k] *= scale
        else:
            for k in others:
                adjusted[k] = 0.0
        adjusted[self.away_label] = floor

        total = sum(adjusted.values()) or 1.0
        return {k: v / total for k, v in adjusted.items()}

    def _cap_activity_probs(self, probs: Dict[str, float]) -> Dict[str, float]:
        """Stop ``work`` / ``relaxing`` / etc. dominating when CLIP sees no person."""
        cap = max(0.0, min(1.0, float(self.activity_prob_cap)))
        out = dict(probs)
        for label in _ACTIVITY_LABELS:
            if label in out and out[label] > cap:
                out[label] = cap
        return out


def _prompts_from_clip_config(clip_prompts: Sequence[str]) -> tuple[list[str], list[str], list[str]]:
    """Split fusion CLIP prompts into person / generic-empty / scene-empty lists."""
    person: list[str] = []
    generic_empty: list[str] = []
    scene_empty: list[str] = []
    for p in clip_prompts:
        low = p.lower().strip()
        if low.startswith("a person ") or low.startswith("an person "):
            person.append(p)
        elif (
            "no people" in low
            or "empty room" in low
            or "unoccupied" in low
            or "empty living room couch" in low
            or "empty bedroom" in low
        ):
            if "couch" in low or "desk" in low or "bedroom" in low or "unoccupied" in low:
                scene_empty.append(p)
            else:
                generic_empty.append(p)
    return person, generic_empty, scene_empty


def build_gate_from_config(
    *,
    occupancy_cfg: Mapping[str, object] | None,
    away_label: str,
    unknown_label: str,
    pose_enabled: bool,
    clip_prompts: Sequence[str] | None = None,
) -> OccupancyGate:
    """Construct an :class:`OccupancyGate` from the (already-merged) YAML config
    sub-section under ``inference.occupancy``. Missing keys fall back to the
    dataclass defaults so the gate is always safe to call."""

    cfg = dict(occupancy_cfg or {})

    def _opt_float(key: str, default: float) -> float:
        v = cfg.get(key)
        if v is None:
            return float(default)
        try:
            return float(v)
        except (TypeError, ValueError):
            return float(default)

    person_prompts = cfg.get("person_prompts")
    empty_prompts = cfg.get("empty_prompts")
    scene_empty_prompts = cfg.get("scene_empty_prompts")
    if clip_prompts:
        auto_person, auto_empty, auto_scene = _prompts_from_clip_config(clip_prompts)
        if not person_prompts and auto_person:
            person_prompts = auto_person
        if not empty_prompts and auto_empty:
            empty_prompts = auto_empty
        if not scene_empty_prompts and auto_scene:
            scene_empty_prompts = auto_scene
    if not person_prompts:
        person_prompts = list(_DEFAULT_PERSON_PROMPTS)
    if not empty_prompts:
        empty_prompts = list(_DEFAULT_EMPTY_PROMPTS)
    if not scene_empty_prompts:
        scene_empty_prompts = list(_DEFAULT_SCENE_EMPTY_PROMPTS)

    enabled = bool(cfg.get("enabled", True))

    return OccupancyGate(
        away_label=str(cfg.get("away_label", away_label)),
        unknown_label=str(cfg.get("unknown_label", unknown_label)),
        person_prompts=list(person_prompts),
        empty_prompts=list(empty_prompts),
        scene_empty_prompts=list(scene_empty_prompts),
        empty_margin=_opt_float("empty_margin", 0.015),
        scene_empty_margin=_opt_float("scene_empty_margin", 0.008),
        motion_max_for_empty=_opt_float("motion_max_for_empty", 0.02),
        motion_min_for_person=_opt_float("motion_min_for_person", 0.012),
        pose_present_floor=_opt_float("pose_present_floor", 0.2),
        away_floor_prob=_opt_float("away_floor_prob", 0.75),
        soft_empty_away_floor_prob=_opt_float("soft_empty_away_floor_prob", 0.55),
        person_absence_clip_max=_opt_float("person_absence_clip_max", 0.24),
        activity_prob_cap=_opt_float("activity_prob_cap", 0.14),
        enabled=enabled,
        pose_enabled=bool(pose_enabled),
    )


__all__ = [
    "OccupancyGate",
    "OccupancyDecision",
    "build_gate_from_config",
]
