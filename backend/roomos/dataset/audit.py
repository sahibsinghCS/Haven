"""Dataset coverage audit for hackathon collection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


@dataclass
class ClassStats:
    label: str
    image_count: int
    estimated_bursts: int
    video_count: int
    images_needed_for_target: int
    ok_for_min_bursts: bool


def estimate_bursts_from_images(image_count: int, frame_count: int = 5, stride: int = 5) -> int:
    if image_count < frame_count:
        return 0
    return 1 + (image_count - frame_count) // stride


def images_needed_for_bursts(target_bursts: int, frame_count: int = 5, stride: int = 5) -> int:
    if target_bursts < 1:
        return frame_count
    return frame_count + (target_bursts - 1) * stride


def _list_images(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def _list_videos(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )


def audit_image_folders(
    images_dir: Path,
    classes: Iterable[str],
    *,
    frame_count: int = 5,
    stride: int = 5,
    min_bursts_per_class: int = 6,
    target_bursts_per_class: int = 12,
) -> list[ClassStats]:
    stats: list[ClassStats] = []
    for label in classes:
        images = _list_images(images_dir / label)
        bursts = estimate_bursts_from_images(len(images), frame_count, stride)
        target_images = images_needed_for_bursts(target_bursts_per_class, frame_count, stride)
        stats.append(
            ClassStats(
                label=label,
                image_count=len(images),
                estimated_bursts=bursts,
                video_count=0,
                images_needed_for_target=max(0, target_images - len(images)),
                ok_for_min_bursts=bursts >= min_bursts_per_class,
            )
        )
    return stats


def audit_video_folders(
    raw_dir: Path,
    classes: Iterable[str],
) -> list[ClassStats]:
    stats: list[ClassStats] = []
    for label in classes:
        videos = _list_videos(raw_dir / label)
        stats.append(
            ClassStats(
                label=label,
                image_count=0,
                estimated_bursts=0,
                video_count=len(videos),
                images_needed_for_target=0,
                ok_for_min_bursts=len(videos) >= 1,
            )
        )
    return stats


def format_audit_report(
    image_stats: list[ClassStats],
    *,
    min_bursts: int,
    target_bursts: int,
    frame_count: int = 5,
    stride: int = 5,
) -> str:
    lines = [
        "RoomOS dataset audit (still images)",
        f"  burst settings: {frame_count} frames, stride {stride} between burst starts",
        f"  minimum: {min_bursts} bursts/class | target: {target_bursts} bursts/class",
        "",
        f"{'class':<10} {'images':>7} {'bursts':>7} {'need+':>7} {'status':>8}",
        "-" * 44,
    ]
    for s in image_stats:
        status = "OK" if s.estimated_bursts >= target_bursts else ("min OK" if s.ok_for_min_bursts else "LOW")
        lines.append(
            f"{s.label:<10} {s.image_count:>7} {s.estimated_bursts:>7} {s.images_needed_for_target:>7} {status:>8}"
        )
    thin = [s.label for s in image_stats if not s.ok_for_min_bursts]
    if thin:
        need = images_needed_for_bursts(min_bursts, frame_count, stride)
        lines.append("")
        lines.append(f"Below minimum ({min_bursts} bursts): {', '.join(thin)}")
        lines.append(f"  -> capture ~{need} stills per thin class: npm run data:capture-stills")
    return "\n".join(lines)
