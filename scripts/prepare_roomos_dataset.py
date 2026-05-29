#!/usr/bin/env python3
"""Build unified RoomOS metadata from downloaded external datasets.

Reads manifests/datasets.yaml and manifests/label_mapping.yaml, scans local
paths, maps source labels to target room states without silently relabeling
ambiguous samples.

Usage (repo root):
  python scripts/prepare_roomos_dataset.py
  python scripts/prepare_roomos_dataset.py --format jsonl --out data/processed/roomos_unified.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifests" / "datasets.yaml"
MAPPING_PATH = ROOT / "manifests" / "label_mapping.yaml"
DEFAULT_OUT = ROOT / "data" / "processed" / "roomos_unified.jsonl"


@dataclass
class UnifiedRecord:
    dataset_id: str
    source_path: str
    source_label: str
    roomos_label: str
    mapping_confidence: str  # high | medium | low
    mapping_status: str  # mapped | uncertain | discard | unmapped
    ambiguous: bool
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_path(local_path: str) -> Path:
    p = Path(local_path)
    return p if p.is_absolute() else ROOT / p


def apply_rules(
    source_label: str,
    rules: list[dict[str, Any]],
) -> Optional[UnifiedRecord]:
    norm = source_label.strip().lower()
    for rule in rules:
        match = str(rule.get("match", "")).strip().lower()
        if norm == match or match in norm:
            target = rule["target"]
            conf = rule.get("confidence", "medium")
            status = "discard" if target == "discard" else "mapped"
            ambiguous = target == "uncertain" or conf == "low"
            return UnifiedRecord(
                dataset_id="",
                source_path="",
                source_label=source_label,
                roomos_label=target,
                mapping_confidence=conf,
                mapping_status=status,
                ambiguous=ambiguous,
                provenance={"rule_match": match, "notes": rule.get("notes")},
            )
    return None


def apply_keyword_rules(
    source_label: str,
    cfg: dict[str, Any],
) -> UnifiedRecord:
    text = source_label.lower()
    for pat in cfg.get("discard_patterns", []):
        if pat.lower() in text:
            return UnifiedRecord(
                dataset_id="",
                source_path="",
                source_label=source_label,
                roomos_label="discard",
                mapping_confidence="high",
                mapping_status="discard",
                ambiguous=False,
                provenance={"matched_discard_pattern": pat},
            )
    for rule in cfg.get("keyword_rules", []):
        for pat in rule.get("patterns", []):
            if pat.lower() in text:
                target = rule["target"]
                conf = rule.get("confidence", "medium")
                return UnifiedRecord(
                    dataset_id="",
                    source_path="",
                    source_label=source_label,
                    roomos_label=target,
                    mapping_confidence=conf,
                    mapping_status="mapped" if target != "uncertain" else "uncertain",
                    ambiguous=target == "uncertain" or conf == "low",
                    provenance={"keyword": pat},
                )
    default = cfg.get("default", "uncertain")
    return UnifiedRecord(
        dataset_id="",
        source_path="",
        source_label=source_label,
        roomos_label=default,
        mapping_confidence="low",
        mapping_status="uncertain",
        ambiguous=True,
        provenance={"reason": "no_rule_match"},
    )


def map_label(dataset_id: str, source_label: str, mapping: dict[str, Any]) -> UnifiedRecord:
    ds_cfg = mapping.get("datasets", {}).get(dataset_id, {})
    rules = ds_cfg.get("rules")
    if rules:
        hit = apply_rules(source_label, rules)
        if hit:
            rec = hit
            rec.dataset_id = dataset_id
            return rec
    if "keyword_rules" in ds_cfg or "default" in ds_cfg:
        rec = apply_keyword_rules(source_label, ds_cfg)
        rec.dataset_id = dataset_id
        return rec
    return UnifiedRecord(
        dataset_id=dataset_id,
        source_path="",
        source_label=source_label,
        roomos_label="uncertain",
        mapping_confidence="low",
        mapping_status="unmapped",
        ambiguous=True,
        provenance={"reason": "no_mapping_config"},
    )


def _indoor_action_roots(raw_dir: Path) -> list[Path]:
    roots = [raw_dir]
    nested = raw_dir / "IndoorActionDataset-video"
    if nested.is_dir():
        roots.append(nested)
    return roots


def iter_indoor_action_clips(raw_dir: Path) -> Iterator[tuple[str, str]]:
    """Infer labels from clip filenames (action in folder or filename)."""
    for root in _indoor_action_roots(raw_dir):
        for split in ("train", "validation", "test"):
            split_dir = root / split
            if not split_dir.is_dir():
                continue
            for path in split_dir.rglob("*.mp4"):
                name = path.stem.lower()
                for action in (
                    "watching tv",
                    "eating",
                    "cleaning",
                    "walking",
                    "sitting down",
                    "standing up",
                    "no-action",
                    "lying on the floor",
                    "falling down",
                    "blowing nose",
                ):
                    if action.replace(" ", "") in name.replace(" ", "") or action in name:
                        yield str(path.relative_to(ROOT)), action
                        break
                else:
                    yield str(path.relative_to(ROOT)), "unknown_clip"


def iter_uci_rows(raw_dir: Path) -> Iterator[tuple[str, str]]:
    for name in ("datatraining.txt", "datatest.txt", "datatest2.txt"):
        p = raw_dir / name
        if not p.exists():
            continue
        with p.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                continue
            # Strip quotes from UCI CSV headers/cells
            header = [h.strip().strip('"') for h in header]
            occ_idx = header.index("Occupancy") if "Occupancy" in header else -1
            for i, row in enumerate(reader):
                if occ_idx < 0 or len(row) <= occ_idx:
                    continue
                cell = row[occ_idx].strip().strip('"')
                yield f"{name}#row{i}", cell


def iter_hf_classification_samples(raw_dir: Path, label_field: str = "ground_truth") -> Iterator[tuple[str, str]]:
    """Best-effort scan of Hugging Face snapshot trees (metadata json / parquet)."""
    for meta in raw_dir.rglob("*.json"):
        if meta.name not in ("dataset_info.json", "metadata.json"):
            continue
    for path in raw_dir.rglob("*.parquet"):
        try:
            import pyarrow.parquet as pq  # type: ignore
        except ImportError:
            return
        table = pq.read_table(path)
        df = table.to_pandas()
        label_col = None
        for col in ("activity", "ground_truth", "label", "category"):
            if col in df.columns:
                label_col = col
                break
        if not label_col:
            continue
        for i, val in enumerate(df[label_col].astype(str).head(5000)):
            yield f"{path.name}#row{i}", val
        return


def scan_dataset(
    entry: dict[str, Any],
    mapping: dict[str, Any],
) -> list[UnifiedRecord]:
    dataset_id = entry["id"]
    status = entry.get("access_status", "pending")
    if status not in ("downloaded", "partial"):
        return []

    raw = resolve_path(entry["local_path"])
    if not raw.exists():
        return []

    records: list[UnifiedRecord] = []
    pairs: Iterable[tuple[str, str]] = []

    if dataset_id == "indoor_action_dataset":
        pairs = iter_indoor_action_clips(raw)
    elif dataset_id == "uci_occupancy_detection":
        pairs = iter_uci_rows(raw)
    elif dataset_id in ("mpii_human_pose_hf", "indoor_scene_recognition_hf"):
        pairs = iter_hf_classification_samples(raw)
    elif dataset_id == "slp_code":
        return []  # code-only; no labeled media in repo

    for source_path, source_label in pairs:
        rec = map_label(dataset_id, source_label, mapping)
        rec.source_path = source_path
        records.append(rec)

    return records


def write_jsonl(path: Path, records: list[UnifiedRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")


def write_csv(path: Path, records: list[UnifiedRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(UnifiedRecord.__dataclass_fields__.keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for rec in records:
            row = rec.to_dict()
            row["provenance"] = json.dumps(row["provenance"])
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare unified RoomOS dataset metadata")
    parser.add_argument("--format", choices=("jsonl", "csv"), default="jsonl")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    manifest = load_yaml(MANIFEST_PATH)
    mapping = load_yaml(MAPPING_PATH)

    all_records: list[UnifiedRecord] = []
    summary: dict[str, int] = {}

    for entry in manifest.get("datasets", []):
        recs = scan_dataset(entry, mapping)
        all_records.extend(recs)
        summary[entry["id"]] = len(recs)

    out = args.out
    if args.format == "jsonl":
        write_jsonl(out, all_records)
    else:
        write_csv(out.with_suffix(".csv"), all_records)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_records": len(all_records),
        "per_dataset": summary,
        "output": str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out),
    }
    report_path = ROOT / "data" / "processed" / "prepare_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
