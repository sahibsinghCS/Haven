"""Minimal keyboard-driven labeling tool.

Plays a video and lets the user assign an activity label to **time ranges**
(wall-clock in the file). Feature export turns the video into **bursts**;
`label_for_burst` attaches a label to each burst row by overlap with these
segments. Segments are written to CSV (see ``schemas.py``).

Controls
--------
* ``SPACE``     pause / resume
* ``→``         step forward (~1s)
* ``←``         step backward (~1s)
* ``[``         mark current time as segment start
* ``]``         mark current time as segment end + commit pending label
* digit keys    select label by index in the class list (1..9)
* ``u``         undo last committed segment
* ``s``         save now
* ``q``         quit (auto-saves)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence

from ..utils.logging import get_logger
from .schemas import LabelSegment, load_label_segments, save_label_segments

log = get_logger("roomos.dataset.labeling")


def run_labeling_ui(
    video_path: str | Path,
    *,
    classes: Sequence[str],
    out_csv: str | Path,
    source_id: Optional[str] = None,
    playback_fps: float = 25.0,
) -> List[LabelSegment]:
    """Launch the labeling UI on a video file."""
    import cv2

    vp = Path(video_path)
    if not vp.exists():
        raise FileNotFoundError(vp)

    sid = source_id or vp.name
    out = Path(out_csv)
    existing = [s for s in load_label_segments(out)]
    segments: List[LabelSegment] = list(existing)
    log.info("Loaded %d existing segments from %s", len(existing), out)

    cap = cv2.VideoCapture(str(vp))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video {vp}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = n_frames / max(src_fps, 1e-3)
    log.info("Video %s — %.1fs @ %.1ffps (%d frames)", vp.name, duration, src_fps, n_frames)
    log.info("Classes: %s", ", ".join(f"{i + 1}={c}" for i, c in enumerate(classes)))

    pending_start: Optional[float] = None
    pending_class: Optional[str] = None
    cur_pos = 0   # current frame index
    paused = False

    def current_time() -> float:
        return cur_pos / max(src_fps, 1e-3)

    def label_to_color(label: str) -> tuple[int, int, int]:
        # Deterministic colors per class index.
        try:
            idx = list(classes).index(label)
        except ValueError:
            return (200, 200, 200)
        palette = [
            (66, 165, 245), (102, 187, 106), (255, 167, 38),
            (171, 71, 188), (239, 83, 80), (38, 198, 218),
            (255, 213, 79), (141, 110, 99), (120, 144, 156),
        ]
        return palette[idx % len(palette)]

    win = "roomos label — q quit | space pause | [ mark-start | ] commit | digits class | u undo | s save"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, cur_pos))
        ok, frame = cap.read()
        if not ok or frame is None:
            cur_pos = max(0, cur_pos - 1)
            ok, frame = cap.read()
            if not ok or frame is None:
                break

        overlay = frame.copy()
        h, w = overlay.shape[:2]
        cv2.rectangle(overlay, (0, 0), (w, 80), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        t = current_time()
        cv2.putText(
            frame,
            f"t={t:6.2f}s / {duration:6.2f}s   pending_start={pending_start}   class={pending_class}   segs={len(segments)}",
            (12, 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            "  ".join(f"{i + 1}:{c}" for i, c in enumerate(classes)),
            (12, 58),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            1,
            cv2.LINE_AA,
        )

        # Color bar of segments along the bottom.
        bar_h = 12
        cv2.rectangle(frame, (0, h - bar_h), (w, h), (40, 40, 40), -1)
        for s in segments:
            if s.source != sid:
                continue
            x0 = int((s.start_sec / max(duration, 1e-3)) * w)
            x1 = int((s.end_sec / max(duration, 1e-3)) * w)
            cv2.rectangle(frame, (x0, h - bar_h), (max(x0 + 2, x1), h), label_to_color(s.label), -1)
        # Cursor line.
        cx = int((t / max(duration, 1e-3)) * w)
        cv2.rectangle(frame, (cx - 1, h - bar_h), (cx + 1, h), (255, 255, 255), -1)

        cv2.imshow(win, frame)

        delay = int(1000 / max(playback_fps, 1.0)) if not paused else 50
        key = cv2.waitKey(delay) & 0xFF

        if key == ord("q"):
            break
        if key == ord(" "):
            paused = not paused
        elif key in (ord("d"), 83):  # right arrow on some platforms
            cur_pos = min(n_frames - 1, cur_pos + int(src_fps))
        elif key in (ord("a"), 81):  # left arrow on some platforms
            cur_pos = max(0, cur_pos - int(src_fps))
        elif key == ord("["):
            pending_start = t
            log.info("pending_start <- %.2fs", t)
        elif key == ord("]"):
            if pending_start is None:
                log.warning("Press [ to mark a start first.")
            elif pending_class is None:
                log.warning("Choose a class (digit key 1..%d) before committing.", len(classes))
            else:
                start = min(pending_start, t)
                end = max(pending_start, t)
                if end - start < 0.05:
                    log.warning("Segment too short (%.3fs); ignored.", end - start)
                else:
                    segments.append(
                        LabelSegment(
                            source=sid,
                            start_sec=start,
                            end_sec=end,
                            label=pending_class,
                            notes="",
                        )
                    )
                    log.info(
                        "committed %s [%.2f .. %.2f] (total=%d)",
                        pending_class, start, end, len(segments),
                    )
                pending_start = None
        elif key == ord("u"):
            if segments and segments[-1].source == sid:
                last = segments.pop()
                log.info("undo: removed %s [%.2f .. %.2f]", last.label, last.start_sec, last.end_sec)
        elif key == ord("s"):
            save_label_segments(out, segments)
            log.info("saved %d segments -> %s", len(segments), out)
        elif ord("1") <= key <= ord("9"):
            idx = key - ord("1")
            if idx < len(classes):
                pending_class = classes[idx]
                log.info("pending_class <- %s", pending_class)

        if not paused:
            cur_pos = min(n_frames - 1, cur_pos + max(1, int(round(src_fps / playback_fps))))

    cap.release()
    cv2.destroyAllWindows()
    save_label_segments(out, segments)
    log.info("saved %d segments -> %s", len(segments), out)
    return segments
