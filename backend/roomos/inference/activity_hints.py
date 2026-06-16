"""CLIP-based nudges for confused activity pairs (work / gaming / relaxing).

XGBoost on multi-room stills often confuses desk+laptop scenes with couch/TV
scenes. Object- and activity-specific CLIP prompts are already in the fused
feature row; this module applies small, renormalized probability shifts when
those prompts disagree with the classifier head — cheap at runtime, no extra
model download.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, MutableMapping, Sequence


def _slugify_prompt(p: str) -> str:
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


def _key(prompt: str, suffix: str = "_mean") -> str:
    return f"clip_sim__{_slugify_prompt(prompt)}{suffix}"


# Object / activity prompts aligned with configs/default.yaml
_GAMING_OBJECT = "a large gaming monitor displaying a colourful video game"
_CONSOLE = "a video game console with controllers connected to a television"
_WORK_DESK = "a tidy work desk with a monitor and a notebook"
_WORK_LAPTOP = "an open laptop with a document on a desk"
_COUCH = "a cozy sofa with throw pillows and a blanket"
_PERSON_WORK = "a person sitting at a desk working on a computer"
_PERSON_GAMING = "a person playing video games with a controller"
_PERSON_RELAX = "a person watching television and relaxing"
_READING_COUCH = "a person reading a book on a couch"
_READING_BED = "a person reading a book in bed"
_STUDY_TEXTBOOKS = "a student studying at a desk with laptop and textbooks"


@dataclass
class ActivityHintConfig:
    enabled: bool = True
    nudge_strength: float = 0.24
    min_margin: float = 0.012
    min_top_prob: float = 0.12


@dataclass
class ActivityHintGate:
    """Apply pairwise CLIP hints on top of classifier probabilities."""

    cfg: ActivityHintConfig = field(default_factory=ActivityHintConfig)
    activity_labels: Sequence[str] = ("work", "sleep", "gaming", "relaxing")

    def apply(
        self,
        probs: Mapping[str, float],
        features: Mapping[str, float],
    ) -> Dict[str, float]:
        out: Dict[str, float] = {k: max(0.0, float(v)) for k, v in probs.items()}
        if not self.cfg.enabled:
            return out

        gaming_obj = _f(features, _GAMING_OBJECT)
        console = _f(features, _CONSOLE)
        work_desk = _f(features, _WORK_DESK)
        work_laptop = _f(features, _WORK_LAPTOP)
        couch = _f(features, _COUCH)
        person_work = _f(features, _PERSON_WORK)
        person_gaming = _f(features, _PERSON_GAMING)
        person_relax = _f(features, _PERSON_RELAX)
        reading_scene = max(_f(features, _READING_COUCH), _f(features, _READING_BED))
        study_scene = _f(features, _STUDY_TEXTBOOKS)

        gaming_scene = max(gaming_obj, console, person_gaming)
        work_scene = max(work_desk, work_laptop, person_work, study_scene)
        relax_scene = max(couch, person_relax)

        strength = float(self.cfg.nudge_strength)
        margin = float(self.cfg.min_margin)
        floor = float(self.cfg.min_top_prob)

        # Gaming vs work (monitor/game vs desk/document) — map to work when gaming retired
        if gaming_scene >= work_scene + margin:
            _nudge_pair(out, "work", "relaxing", strength * 0.5, floor)
        elif work_scene >= gaming_scene + margin:
            _nudge_pair(out, "work", "relaxing", strength * 0.35, floor)

        # Relaxing vs work (couch/TV vs desk)
        if relax_scene >= work_scene + margin:
            _nudge_pair(out, "relaxing", "work", strength, floor)
        elif work_scene >= relax_scene + margin:
            _nudge_pair(out, "work", "relaxing", strength * 0.95, floor)

        # Reading vs work — only nudge when the classifier already sees reading and
        # book CLIP clearly beats desk/study (avoids false reading on plain desk).
        if "reading" in out and float(out.get("reading", 0.0)) >= floor:
            desk_work = max(work_desk, work_laptop, person_work)
            study = study_scene
            work_like = max(desk_work, study)
            clip_margin = reading_scene - work_like
            if clip_margin >= margin * 1.5:
                boost = strength * (0.85 + min(0.5, clip_margin * 2.5))
                _nudge_pair(out, "reading", "work", boost, floor)

        total = sum(out.values()) or 1.0
        return {k: v / total for k, v in out.items()}


def build_activity_hints_from_config(
    cfg: Mapping[str, object] | None,
) -> ActivityHintGate:
    raw = dict(cfg or {})
    return ActivityHintGate(
        cfg=ActivityHintConfig(
            enabled=bool(raw.get("enabled", True)),
            nudge_strength=float(raw.get("nudge_strength", 0.22)),
            min_margin=float(raw.get("min_margin", 0.012)),
            min_top_prob=float(raw.get("min_top_prob", 0.12)),
        )
    )


def _f(features: Mapping[str, float], prompt: str) -> float:
    return float(features.get(_key(prompt), 0.0) or 0.0)


def _nudge_pair(
    probs: MutableMapping[str, float],
    boost: str,
    cut: str,
    strength: float,
    floor: float,
) -> None:
    if boost not in probs or cut not in probs:
        return
    if probs[boost] < floor and probs[cut] < floor:
        return
    delta = strength * max(probs[boost], probs[cut], 0.15)
    probs[boost] = probs.get(boost, 0.0) + delta
    probs[cut] = max(0.0, probs.get(cut, 0.0) - delta)


__all__ = ["ActivityHintGate", "ActivityHintConfig", "build_activity_hints_from_config"]
