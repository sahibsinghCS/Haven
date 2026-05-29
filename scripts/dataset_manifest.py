#!/usr/bin/env python3
"""Read/update manifests/datasets.yaml after download attempts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifests" / "datasets.yaml"


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "datasets" not in data:
        data["datasets"] = []
    return data


def save_manifest(data: dict[str, Any], path: Path = MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False, allow_unicode=True)


def update_dataset(
    dataset_id: str,
    *,
    access_status: str | None = None,
    blocker_reason: str | None = None,
    local_path: str | None = None,
    notes: str | None = None,
    path: Path = MANIFEST_PATH,
) -> None:
    data = load_manifest(path)
    found = False
    for entry in data.get("datasets", []):
        if entry.get("id") == dataset_id:
            found = True
            if access_status is not None:
                entry["access_status"] = access_status
            if blocker_reason is not None:
                entry["blocker_reason"] = blocker_reason
            if local_path is not None:
                entry["local_path"] = local_path
            if notes is not None:
                entry["download_notes"] = notes
            break
    if not found:
        raise KeyError(f"Unknown dataset id: {dataset_id}")
    save_manifest(data, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Update dataset manifest status")
    parser.add_argument("dataset_id")
    parser.add_argument("--access-status", required=True)
    parser.add_argument("--blocker-reason", default=None)
    parser.add_argument("--local-path", default=None)
    parser.add_argument("--notes", default=None)
    args = parser.parse_args()
    update_dataset(
        args.dataset_id,
        access_status=args.access_status,
        blocker_reason=args.blocker_reason,
        local_path=args.local_path,
        notes=args.notes,
    )
    print(f"Updated {args.dataset_id} -> {args.access_status}")


if __name__ == "__main__":
    main()
