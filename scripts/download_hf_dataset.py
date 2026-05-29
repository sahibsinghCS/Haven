#!/usr/bin/env python3
"""Download a Hugging Face dataset snapshot into data/raw/."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--local-dir", required=True, type=Path)
    parser.add_argument("--repo-type", default="dataset")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=2,
        help="Parallel downloads (use 1-2 to avoid HF rate limits).",
    )
    args = parser.parse_args()

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print(
            "huggingface_hub not installed. Run: pip install -r requirements-datasets.txt",
            file=sys.stderr,
        )
        return 1

    args.local_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_download(
        repo_id=args.repo_id,
        repo_type=args.repo_type,
        local_dir=str(args.local_dir),
        max_workers=max(1, args.max_workers),
        resume_download=True,
    )
    print(f"Downloaded {args.repo_id} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
