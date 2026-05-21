"""Dataset schema definitions and label IO.

A "feature row" on disk looks like::

    source, start_time, end_time, num_frames, <feature columns...>, label?

Labels are stored separately as time segments per source video so they can be
edited without re-extracting features::

    source, start_sec, end_sec, label, notes
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

# Mandatory non-feature columns in a features dataframe.
FEATURE_META_COLUMNS: tuple[str, ...] = (
    "source",
    "start_time",
    "end_time",
    "num_frames",
    "burst_index",
)

# Schema of the labels CSV.
LABEL_COLUMNS: tuple[str, ...] = ("source", "start_sec", "end_sec", "label", "notes")


@dataclass(frozen=True)
class LabelSegment:
    source: str
    start_sec: float
    end_sec: float
    label: str
    notes: str = ""

    def covers(self, t: float) -> bool:
        return self.start_sec <= t <= self.end_sec


def load_label_segments(path: str | Path) -> List[LabelSegment]:
    """Load a CSV of segments. Returns an empty list if file doesn't exist."""
    p = Path(path)
    if not p.exists():
        return []
    out: List[LabelSegment] = []
    with p.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in LABEL_COLUMNS[:-1] if c not in reader.fieldnames or []]
        if missing:
            raise ValueError(
                f"Labels file {p} is missing required columns: {missing}. "
                f"Expected at least {LABEL_COLUMNS[:-1]}"
            )
        for row in reader:
            try:
                out.append(
                    LabelSegment(
                        source=str(row["source"]).strip(),
                        start_sec=float(row["start_sec"]),
                        end_sec=float(row["end_sec"]),
                        label=str(row["label"]).strip(),
                        notes=str(row.get("notes") or "").strip(),
                    )
                )
            except (KeyError, ValueError) as e:
                raise ValueError(f"Malformed label row in {p}: {row} ({e})") from e
    return out


def save_label_segments(path: str | Path, segments: Iterable[LabelSegment]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(LABEL_COLUMNS))
        writer.writeheader()
        for s in segments:
            writer.writerow(
                {
                    "source": s.source,
                    "start_sec": f"{s.start_sec:.3f}",
                    "end_sec": f"{s.end_sec:.3f}",
                    "label": s.label,
                    "notes": s.notes,
                }
            )
    return p


def label_for_burst(
    source: str,
    start_time: float,
    end_time: float,
    segments: Sequence[LabelSegment],
    min_overlap_ratio: float = 0.5,
) -> Optional[str]:
    """Pick a label for a burst from overlapping time segments.

    The burst is represented by ``[start_time, end_time]`` (typically the
    first/last subsampled frame timestamps). A segment must overlap this
    interval by at least ``min_overlap_ratio`` of the burst duration; otherwise
    returns ``None`` (unlabeled sample).
    """
    win_len = max(1e-6, end_time - start_time)
    best_label: Optional[str] = None
    best_overlap = 0.0
    for seg in segments:
        if seg.source != source:
            continue
        overlap = max(0.0, min(end_time, seg.end_sec) - max(start_time, seg.start_sec))
        if overlap > best_overlap:
            best_overlap = overlap
            best_label = seg.label
    if best_label is None:
        return None
    if (best_overlap / win_len) < min_overlap_ratio:
        return None
    return best_label
