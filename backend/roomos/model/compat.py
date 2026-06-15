"""Train vs live-inference compatibility — strict gate at engine start."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Sequence

from ..config import Config, load_config
from ..features.fusion import FeatureFusion
from ..utils.io import read_json
from .registry import MODEL_ARTIFACT_FILES, load_model_bundle


class TrainServeCompatibilityError(RuntimeError):
    """Raised when a model bundle cannot be used with the live inference config."""

    def __init__(self, message: str, *, report: Optional["CompatibilityReport"] = None) -> None:
        super().__init__(message)
        self.report = report


@dataclass
class CompatibilityMismatch:
    """One concrete train vs inference difference."""

    category: str  # labels | features | feature_columns | burst
    field: str
    train: str
    inference: str
    detail: str = ""


@dataclass
class CompatibilityReport:
    bundle_dir: str
    inference_config: str
    train_config_source: str
    bundle_classes: List[str]
    inference_classes: List[str]
    n_bundle_columns: int
    n_expected_columns: int
    mismatches: List[CompatibilityMismatch] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.mismatches) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "bundle_dir": self.bundle_dir,
            "inference_config": self.inference_config,
            "train_config_source": self.train_config_source,
            "bundle_classes": self.bundle_classes,
            "inference_classes": self.inference_classes,
            "n_bundle_columns": self.n_bundle_columns,
            "n_expected_columns": self.n_expected_columns,
            "mismatches": [
                {
                    "category": m.category,
                    "field": m.field,
                    "train": m.train,
                    "inference": m.inference,
                    "detail": m.detail,
                }
                for m in self.mismatches
            ],
        }


def _enabled_flags(cfg: Config) -> dict[str, bool]:
    e = cfg.features.enabled
    return {
        "clip": bool(e.get("clip", True)),
        "pose": bool(e.get("pose", True)),
        "motion": bool(e.get("motion", True)),
        "posture": bool(e.get("posture", True)),
    }


def expected_feature_columns(cfg: Config) -> List[str]:
    """Column names the fusion layer would emit for this config (no model weights loaded)."""
    f = cfg.features
    enabled = _enabled_flags(cfg)
    prompts: Sequence[str] = list(f.clip.get("prompts", [])) if enabled["clip"] else []
    grid = tuple(f.motion.get("grid", [4, 4])) if enabled["motion"] else (0, 0)
    motion_cells = int(grid[0] * grid[1]) if grid[0] and grid[1] else 0
    fusion = FeatureFusion(
        prompt_labels=prompts,
        motion_grid_size=motion_cells,
        use_clip=enabled["clip"],
        use_pose=enabled["pose"],
        use_motion=enabled["motion"],
        use_posture=enabled["posture"],
    )
    return list(fusion.feature_names)


def resolve_model_bundle_dir(infer_cfg: Config) -> Path:
    raw = (infer_cfg.get("inference", {}) or {}).get("model_dir", "data/models/latest")
    p = Path(raw)
    return p if p.is_absolute() else infer_cfg.resolve_path(p)


def _train_config_from_bundle(bundle: Path) -> tuple[Config, str]:
    train_raw = read_json(bundle / "train_config.json")
    src = train_raw.get("_source_config")
    if src and Path(src).exists():
        return load_config(src), str(Path(src).resolve())
    return Config(raw=train_raw), "(embedded train_config.json)"


def _registry_label_check(bundle_classes: List[str]) -> List[CompatibilityMismatch]:
    """Dynamic-mood label gate.

    With a mood registry the bundle's class list may include deleted moods
    (masked at runtime). Startup fails only when *inference-eligible* labels are
    empty — i.e. no active, ML-enabled mood (or legacy label) the bundle can
    predict for the current registry.
    """
    from ..moods.registry import active_mood_ids, inference_eligible_labels

    bundle_set = set(bundle_classes)
    eligible = inference_eligible_labels(bundle_classes=bundle_set) - {"unknown"}
    if eligible:
        return []
    active = sorted(active_mood_ids())
    return [
        CompatibilityMismatch(
            category="labels",
            field="inference eligible labels",
            train=str(sorted(bundle_classes)),
            inference=f"eligible: [] (active moods: {active})",
            detail=(
                "Deployed model cannot predict any active mood. Collect data, "
                "train from Moods / Preferences, or restore a builtin the bundle knows."
            ),
        )
    ]


def _compare_labels(bundle_classes: List[str], infer_classes: List[str]) -> List[CompatibilityMismatch]:
    try:
        from ..moods.registry import registry_exists

        if registry_exists():
            return _registry_label_check(bundle_classes)
    except Exception:
        pass
    out: List[CompatibilityMismatch] = []
    if list(bundle_classes) != list(infer_classes):
        out.append(
            CompatibilityMismatch(
                category="labels",
                field="classes (order matters for XGBoost)",
                train=str(list(bundle_classes)),
                inference=str(list(infer_classes)),
                detail="Retrain after aligning configs/default.yaml labels.classes with the UI.",
            )
        )
    bundle_set = set(bundle_classes)
    infer_set = set(infer_classes)
    if bundle_set != infer_set:
        only_train = sorted(bundle_set - infer_set)
        only_infer = sorted(infer_set - bundle_set)
        out.append(
            CompatibilityMismatch(
                category="labels",
                field="class set",
                train=f"only in bundle: {only_train}" if only_train else "same set",
                inference=f"only in inference config: {only_infer}" if only_infer else "same set",
            )
        )
    return out


def _compare_feature_modules(train_cfg: Config, infer_cfg: Config) -> List[CompatibilityMismatch]:
    out: List[CompatibilityMismatch] = []
    t_flags = _enabled_flags(train_cfg)
    i_flags = _enabled_flags(infer_cfg)
    for key in ("clip", "pose", "motion", "posture"):
        if t_flags[key] != i_flags[key]:
            out.append(
                CompatibilityMismatch(
                    category="features",
                    field=f"features.enabled.{key}",
                    train="enabled" if t_flags[key] else "disabled",
                    inference="enabled" if i_flags[key] else "disabled",
                    detail="Train and live inference must extract the same modules.",
                )
            )
    t_prompts = list(train_cfg.features.clip.get("prompts", [])) if t_flags["clip"] else []
    i_prompts = list(infer_cfg.features.clip.get("prompts", [])) if i_flags["clip"] else []
    if t_prompts != i_prompts:
        out.append(
            CompatibilityMismatch(
                category="features",
                field="features.clip.prompts",
                train=f"{len(t_prompts)} prompts",
                inference=f"{len(i_prompts)} prompts",
                detail="Prompt list/order defines clip_sim__* column names.",
            )
        )
    t_grid = tuple(train_cfg.features.motion.get("grid", [4, 4]))
    i_grid = tuple(infer_cfg.features.motion.get("grid", [4, 4]))
    if t_flags["motion"] and t_grid != i_grid:
        out.append(
            CompatibilityMismatch(
                category="features",
                field="features.motion.grid",
                train=str(t_grid),
                inference=str(i_grid),
            )
        )
    return out


def _compare_burst(train_cfg: Config, infer_cfg: Config) -> List[CompatibilityMismatch]:
    out: List[CompatibilityMismatch] = []
    b = train_cfg.burst
    i = infer_cfg.burst
    pairs = [
        ("frame_count", int(b.frame_count), int(i.frame_count)),
        ("duration_seconds", float(b.duration_seconds), float(i.duration_seconds)),
        ("stride_seconds", float(b.stride_seconds), float(i.stride_seconds)),
        ("sampling_strategy", str(b.sampling_strategy), str(i.sampling_strategy)),
        ("min_collected_frames", int(b.min_collected_frames), int(i.min_collected_frames)),
    ]
    for name, tv, iv in pairs:
        if tv != iv:
            out.append(
                CompatibilityMismatch(
                    category="burst",
                    field=f"burst.{name}",
                    train=str(tv),
                    inference=str(iv),
                    detail="Burst timing changes fused statistics; retrain after aligning burst settings.",
                )
            )
    return out


def _compare_feature_columns(
    trained_cols: List[str], infer_cfg: Config
) -> List[CompatibilityMismatch]:
    expected = expected_feature_columns(infer_cfg)
    trained_set = set(trained_cols)
    expected_set = set(expected)
    out: List[CompatibilityMismatch] = []
    if trained_set != expected_set:
        missing = sorted(expected_set - trained_set)
        extra = sorted(trained_set - expected_set)
        if missing:
            preview = ", ".join(missing[:8])
            suffix = f" (+{len(missing) - 8} more)" if len(missing) > 8 else ""
            out.append(
                CompatibilityMismatch(
                    category="feature_columns",
                    field="missing in bundle",
                    train="(absent)",
                    inference=f"{len(missing)} columns e.g. {preview}{suffix}",
                    detail="Live fusion will produce columns the model never saw.",
                )
            )
        if extra:
            preview = ", ".join(extra[:8])
            suffix = f" (+{len(extra) - 8} more)" if len(extra) > 8 else ""
            out.append(
                CompatibilityMismatch(
                    category="feature_columns",
                    field="extra in bundle",
                    train=f"{len(extra)} columns e.g. {preview}{suffix}",
                    inference="(not produced live)",
                    detail="Model expects features live inference no longer computes.",
                )
            )
    return out


def build_compatibility_report(
    bundle_dir: str | Path,
    *,
    inference_config: str | Path = "configs/inference.yaml",
    train_config: Config | None = None,
    train_config_source: str | None = None,
) -> CompatibilityReport:
    """Build a structured compatibility report (does not raise)."""
    bundle = Path(bundle_dir)
    infer_cfg = load_config(inference_config)
    infer_classes = list(infer_cfg.labels.classes)

    for name in MODEL_ARTIFACT_FILES:
        if not (bundle / name).exists():
            return CompatibilityReport(
                bundle_dir=str(bundle.resolve()),
                inference_config=str(Path(inference_config).resolve()),
                train_config_source="(missing bundle)",
                bundle_classes=[],
                inference_classes=infer_classes,
                n_bundle_columns=0,
                n_expected_columns=len(expected_feature_columns(infer_cfg)),
                mismatches=[
                    CompatibilityMismatch(
                        category="bundle",
                        field=name,
                        train="missing",
                        inference="required",
                        detail="Run: npm run train:demo",
                    )
                ],
            )

    model = load_model_bundle(bundle)
    if train_config is None:
        train_config, src = _train_config_from_bundle(bundle)
        train_config_source = train_config_source or src
    else:
        train_config_source = train_config_source or "(provided)"

    mismatches: List[CompatibilityMismatch] = []
    mismatches.extend(_compare_labels(model.classes, infer_classes))
    mismatches.extend(_compare_feature_modules(train_config, infer_cfg))
    mismatches.extend(_compare_burst(train_config, infer_cfg))
    mismatches.extend(_compare_feature_columns(model.feature_columns, infer_cfg))

    return CompatibilityReport(
        bundle_dir=str(bundle.resolve()),
        inference_config=str(Path(inference_config).resolve()),
        train_config_source=train_config_source,
        bundle_classes=list(model.classes),
        inference_classes=infer_classes,
        n_bundle_columns=len(model.feature_columns),
        n_expected_columns=len(expected_feature_columns(infer_cfg)),
        mismatches=mismatches,
    )


def format_compatibility_error(report: CompatibilityReport) -> str:
    """Human-readable, actionable error for API/UI."""
    lines = [
        "Live engine blocked: model bundle is not compatible with inference config.",
        "",
        f"  Model bundle:      {report.bundle_dir}",
        f"  Inference config:  {report.inference_config}",
        f"  Trained with:      {report.train_config_source}",
        "",
    ]

    by_cat: dict[str, List[CompatibilityMismatch]] = {}
    for m in report.mismatches:
        by_cat.setdefault(m.category, []).append(m)

    section_titles = {
        "bundle": "Bundle artifacts",
        "labels": "Labels",
        "features": "Feature modules (clip / pose / motion / posture)",
        "feature_columns": "Feature columns",
        "burst": "Burst settings",
    }

    for cat in ("bundle", "labels", "features", "feature_columns", "burst"):
        items = by_cat.get(cat)
        if not items:
            continue
        lines.append(f"[{section_titles.get(cat, cat)}]")
        for m in items:
            lines.append(f"  {m.field}:")
            lines.append(f"    train:      {m.train}")
            lines.append(f"    inference:  {m.inference}")
            if m.detail:
                lines.append(f"    note:       {m.detail}")
        lines.append("")

    if not report.mismatches:
        lines.append("(no mismatches listed — unexpected)")
    else:
        lines.extend(
            [
                "Fix (recommended):",
                "  cd backend",
                "  npm run train:demo          # from repo root — synthetic bootstrap",
                "  npm run train:images        # data/raw_images/<label>/*.jpg",
                "  npm run train:videos        # data/raw/<label>/*.mp4",
                "",
                "Configs must match:",
                "  Train with:  configs/train_personal.yaml  (or train_roomos.py)",
                "  Live uses:   configs/inference.yaml",
                "",
                "Verify before starting live:",
                "  npm run train:verify",
            ]
        )
    return "\n".join(lines)


def assert_live_engine_compatible(
    bundle_dir: str | Path,
    *,
    inference_config: str | Path = "configs/inference.yaml",
) -> CompatibilityReport:
    """Strict gate: raise if the bundle cannot run with live inference config."""
    report = build_compatibility_report(bundle_dir, inference_config=inference_config)
    if not report.ok:
        raise TrainServeCompatibilityError(format_compatibility_error(report), report=report)
    return report


def verify_bundle_for_live(
    bundle_dir: str | Path,
    *,
    inference_config: str | Path = "configs/inference.yaml",
    train_config: Config | None = None,
) -> dict[str, Any]:
    """CLI-friendly verify: returns report dict or raises."""
    if train_config is not None:
        report = build_compatibility_report(
            bundle_dir,
            inference_config=inference_config,
            train_config=train_config,
        )
    else:
        report = build_compatibility_report(bundle_dir, inference_config=inference_config)
    if not report.ok:
        raise TrainServeCompatibilityError(format_compatibility_error(report), report=report)
    return report.to_dict()


def gate_live_engine_start(infer_cfg: Config, *, inference_config_path: str | Path) -> CompatibilityReport:
    """Resolve model dir from inference config and run the startup gate."""
    bundle_dir = resolve_model_bundle_dir(infer_cfg)
    return assert_live_engine_compatible(
        bundle_dir,
        inference_config=inference_config_path,
    )


# Backward-compatible helper used in tests
def compare_feature_configs(train_cfg: Config, infer_cfg: Config) -> List[str]:
    mismatches: List[CompatibilityMismatch] = []
    mismatches.extend(_compare_feature_modules(train_cfg, infer_cfg))
    mismatches.extend(_compare_burst(train_cfg, infer_cfg))
    return [f"{m.field}: train={m.train} vs inference={m.inference}" for m in mismatches]


def print_training_success(bundle_dir: Path, *, inference_config: str = "configs/inference.yaml") -> None:
    """Post-train checklist for hackathon operators."""
    lines = [
        "",
        "Training finished successfully.",
        f"  Model bundle: {bundle_dir.resolve()}",
        "  Artifacts: model.json, label_encoder.json, feature_columns.json, metrics.json",
        "",
        "Next steps:",
        f"  1. Verify live compatibility:  npm run train:verify",
        "  2. Start API + UI:             npm run dev   (from repo root)",
        "  3. Open live view:             http://127.0.0.1:3000/live",
        "",
        f"Live inference reads: {inference_config} -> inference.model_dir",
    ]
    print("\n".join(lines))
