"""Source WIDE, whole-room sleep photos from Pexels + Unsplash.

RoomOS runs on a webcam that sees the *whole room* (zoomed out), so sleep
training images should look the same: a wide bedroom scene with a person
clearly **asleep** in bed -- not a tight close-up of a face/hand, and not an
awake person in bed.

For each candidate this importer enforces three things:

1. **Actually sleeping** -- CLIP gate (asleep-in-bed prompts beat awake / floor /
   couch / empty-bed / baby prompts) AND the provider's own caption must not look
   awake ("reading", "phone", "awake", "making the bed", ...). Captions that say
   "sleeping/asleep/napping" are preferred.
2. **Whole room / zoomed out** -- landscape orientation from the API, plus a
   framing check: reject tight close-ups using (a) CLIP wide-shot vs close-up
   prompts and (b) MediaPipe person-bbox area fraction when a body is detected.
3. **Not a duplicate** -- perceptual average-hash (robust to re-encoding) against
   everything already kept OR rejected, so reruns never re-add removed images.

License-safe: Pexels License and Unsplash License are both free to use
(commercial OK). Keepers are written as ``person_sleeping_bed_NNN.jpg`` into BOTH
``data/base_images/sleep/`` and ``data/raw_images/sleep/`` and recorded in
``data/base_images/_manifests/sleep_manifest.csv``.

Run from ``backend/``::

    python scripts/import_sleep_web.py --provider both --target 120 \
        --pexels-key <K> --unsplash-key <K>
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import csv
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import typer

from roomos.config import load_config
from roomos.features.clip_extractor import ClipExtractor
from roomos.utils.io import ensure_dir
from roomos.utils.logging import get_logger, setup_logging

from clean_sleep_bed import BED_BAD, BED_GOOD

try:  # safe console on Windows (unicode photographer names)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

DEFAULT_CONFIG = Path("configs/inference.yaml")
NAME_PREFIX = "person_sleeping_bed"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

PEXELS_SEARCH = "https://api.pexels.com/v1/search"
UNSPLASH_SEARCH = "https://api.unsplash.com/search/photos"
PEXELS_LICENSE = "Pexels License (free to use, commercial OK, attribution not required)"
UNSPLASH_LICENSE = "Unsplash License (free to use, commercial OK, attribution appreciated)"

log = get_logger("roomos.scripts.import_sleep_web")

AWAKE_BAD = [
    "a person awake in bed looking at a smartphone",
    "a person sitting up awake in bed reading a book",
    "a person awake and smiling in bed",
    "a person awake watching television in bed",
    "a person sitting upright on the bed awake",
    "an empty unmade bed with no person",
    "an empty neatly made bed in a bedroom",
    "a close-up of bedding and sheets with no person",
    "a made bed with decorative pillows and no person",
    "a person making the bed",
    "a person arranging pillows on a bed",
    "hands smoothing a bedsheet",
    "folded laundry and towels on a bed",
    "a cup of coffee on a bed in the morning",
    "a person wrapped in a blanket standing in a studio",
    "a person sitting wrapped in a blanket against a white wall",
]
# Framing prompts: wide whole-room vs tight close-up.
WIDE_PROMPTS = [
    "a wide shot of a whole bedroom with a person asleep in bed",
    "a full view of a bedroom interior with a person sleeping in bed",
    "a person sleeping in bed seen from across the room",
]
CLOSEUP_PROMPTS = [
    "a close-up of a sleeping person's face",
    "an extreme close-up of a person in bed",
    "a tight crop of hands on bedding",
]

# Caption text hints (provider alt/description).
CAPTION_SLEEP = ("sleep", "asleep", "napping", "dozing", "slumber")
CAPTION_AWAKE = (
    "awake", "reading", "phone", "laptop", "coffee", "making the bed",
    "make the bed", "working", "wake up",
)

DEFAULT_QUERIES = [
    "bedroom interior person sleeping in bed",
    "wide bedroom man sleeping in bed",
    "wide bedroom woman sleeping in bed",
    "person asleep in bed messy bedroom",
    "couple sleeping in bed bedroom",
    "person sleeping in bed morning light bedroom",
    "person sleeping under blanket bedroom interior",
    "teenager sleeping in bedroom bed",
    "person sleeping in hotel room bed",
    "person sleeping in bed night bedroom",
    "wide angle bedroom person sleeping in bed",
    "hotel bedroom person asleep in bed",
    "dorm room person sleeping in bunk bed",
    "person sleeping in bed cozy bedroom interior",
    "messy bedroom person sleeping in bed",
    "woman asleep bed room interior",
    "man asleep bedroom wide shot",
    "person sleeping dorm room bed",
    "person sleeping daytime bedroom window",
    "tired person sleeping bedroom",
]

app = typer.Typer(add_completion=False, help="Import wide whole-room sleep photos (Pexels + Unsplash).")


def _ascii(text: str) -> str:
    return (text or "").encode("ascii", "replace").decode("ascii")


def _ahash(image_bgr: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (8, 8), interpolation=cv2.INTER_AREA)
    return (g > g.mean()).flatten()


def _is_dup(h: np.ndarray, pool: List[np.ndarray], thresh: int = 6) -> bool:
    for k in pool:
        if int((h != k).sum()) <= thresh:
            return True
    return False


def _existing_max_index(*dirs: Path) -> int:
    pat = re.compile(rf"^{re.escape(NAME_PREFIX)}_(\d+)\b")
    best = -1
    for d in dirs:
        if d.is_dir():
            for p in d.iterdir():
                m = pat.match(p.stem)
                if m:
                    best = max(best, int(m.group(1)))
    return best


def _download(url: str, timeout: float = 30.0) -> Optional[bytes]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RoomOS-data/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:  # pragma: no cover
        log.debug("download failed %s (%s)", url[:80], e)
        return None


# --- providers -------------------------------------------------------------

def _pexels(key: str, query: str, page: int, per_page: int) -> List[dict]:
    params = urllib.parse.urlencode(
        {"query": query, "per_page": per_page, "page": page, "orientation": "landscape", "size": "large"}
    )
    req = urllib.request.Request(
        f"{PEXELS_SEARCH}?{params}", headers={"Authorization": key, "User-Agent": "RoomOS-data/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        import json

        data = json.loads(resp.read().decode("utf-8"))
    out = []
    for p in data.get("photos", []):
        src = p.get("src", {})
        out.append(
            {
                "provider": "pexels",
                "id": str(p.get("id")),
                "url": src.get("large2x") or src.get("large") or src.get("original"),
                "width": int(p.get("width", 0)),
                "height": int(p.get("height", 0)),
                "author": p.get("photographer", ""),
                "page": p.get("url", ""),
                "caption": p.get("alt", "") or "",
                "license": PEXELS_LICENSE,
            }
        )
    return out


def _unsplash(key: str, query: str, page: int, per_page: int) -> List[dict]:
    params = urllib.parse.urlencode(
        {"query": query, "per_page": min(per_page, 30), "page": page, "orientation": "landscape"}
    )
    req = urllib.request.Request(
        f"{UNSPLASH_SEARCH}?{params}",
        headers={
            "Authorization": "Client-ID " + key,
            "User-Agent": "RoomOS-data/1.0",
            "Accept-Version": "v1",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        import json

        remaining = resp.headers.get("X-Ratelimit-Remaining")
        data = json.loads(resp.read().decode("utf-8"))
    if remaining is not None:
        log.debug("unsplash ratelimit remaining=%s", remaining)
    out = []
    for p in data.get("results", []):
        urls = p.get("urls", {})
        raw = urls.get("raw")
        url = (raw + "&w=1400&q=80&fm=jpg") if raw else urls.get("regular")
        out.append(
            {
                "provider": "unsplash",
                "id": str(p.get("id")),
                "url": url,
                "width": int(p.get("width", 0)),
                "height": int(p.get("height", 0)),
                "author": (p.get("user", {}) or {}).get("name", ""),
                "page": (p.get("links", {}) or {}).get("html", ""),
                "caption": p.get("alt_description", "") or p.get("description", "") or "",
                "license": UNSPLASH_LICENSE,
            }
        )
    return out


# --- pose framing ----------------------------------------------------------

class _PoseFraming:
    """Person bbox area fraction via MediaPipe (static image mode)."""

    def __init__(self) -> None:
        self._pose = None
        try:
            import mediapipe as mp

            if hasattr(mp, "solutions"):
                self._pose = mp.solutions.pose.Pose(
                    static_image_mode=True, model_complexity=1, min_detection_confidence=0.5
                )
        except Exception as e:  # pragma: no cover
            log.warning("pose framing unavailable (%s)", e)

    def person_fraction(self, image_bgr: np.ndarray) -> Optional[float]:
        if self._pose is None:
            return None
        res = self._pose.process(image_bgr[:, :, ::-1])
        if not res.pose_landmarks:
            return None
        xs = [lm.x for lm in res.pose_landmarks.landmark if lm.visibility > 0.3]
        ys = [lm.y for lm in res.pose_landmarks.landmark if lm.visibility > 0.3]
        if not xs or not ys:
            return None
        w = max(0.0, min(1.0, max(xs)) - max(0.0, min(xs)))
        h = max(0.0, min(1.0, max(ys)) - max(0.0, min(ys)))
        return float(w * h)

    def close(self) -> None:
        if self._pose is not None:
            try:
                self._pose.close()
            except Exception:
                pass


def _caption_verdict(caption: str) -> str:
    c = caption.lower()
    if any(w in c for w in CAPTION_AWAKE):
        return "awake"
    if any(w in c for w in CAPTION_SLEEP):
        return "sleep"
    return "neutral"


@app.command()
def main(
    provider: str = typer.Option("both", "--provider", help="pexels | unsplash | both"),
    pexels_key: str = typer.Option("", "--pexels-key"),
    unsplash_key: str = typer.Option("", "--unsplash-key"),
    target: int = typer.Option(120, "--target", help="New gated keepers to collect."),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    out_dir: Path = typer.Option(Path("data/base_images"), "--out-dir"),
    raw_dir: Path = typer.Option(Path("data/raw_images"), "--raw-dir"),
    per_page: int = typer.Option(30, "--per-page"),
    max_pages: int = typer.Option(6, "--max-pages"),
    min_short_side: int = typer.Option(480, "--min-short-side"),
    min_aspect: float = typer.Option(1.2, "--min-aspect", help="Require landscape w/h >= this (whole-room)."),
    margin: float = typer.Option(0.02, "--margin", help="CLIP: bad must be below good by this."),
    min_good: float = typer.Option(0.20, "--min-good"),
    max_person_frac: float = typer.Option(0.55, "--max-person-frac", help="Reject if detected body fills more than this fraction (close-up)."),
    framing_margin: float = typer.Option(0.0, "--framing-margin", help="Reject if close-up CLIP prompt beats wide by more than this."),
    require_sleep_caption: bool = typer.Option(False, "--require-sleep-caption", help="Only keep if caption mentions sleeping."),
    sleep_sec: float = typer.Option(0.4, "--sleep-sec"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    provider = provider.strip().lower()
    pk = pexels_key.strip() or os.environ.get("PEXELS_API_KEY", "").strip()
    uk = unsplash_key.strip() or os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
    providers: List[str] = []
    if provider in ("pexels", "both") and pk:
        providers.append("pexels")
    if provider in ("unsplash", "both") and uk:
        providers.append("unsplash")
    if not providers:
        raise typer.BadParameter("No usable provider/key. Pass --pexels-key and/or --unsplash-key.")

    cfg = load_config(config)
    base_root = out_dir if out_dir.is_absolute() else cfg.resolve_path(out_dir)
    raw_root = raw_dir if raw_dir.is_absolute() else cfg.resolve_path(raw_dir)
    sleep_base = ensure_dir(base_root / "sleep")
    sleep_raw = ensure_dir(raw_root / "sleep")
    manifest_dir = ensure_dir(base_root / "_manifests")
    manifest_csv = manifest_dir / "sleep_manifest.csv"

    prompts = BED_GOOD + (BED_BAD + AWAKE_BAD) + WIDE_PROMPTS + CLOSEUP_PROMPTS
    ng = len(BED_GOOD)
    nb = len(BED_BAD + AWAKE_BAD)
    nw = len(WIDE_PROMPTS)
    i_wide0, i_wide1 = ng + nb, ng + nb + nw
    i_close0 = i_wide1

    clip_cfg = dict(cfg.features.get("clip", {}))
    extractor = ClipExtractor(
        model_name=str(clip_cfg.get("model_name", "ViT-B-32")),
        pretrained=str(clip_cfg.get("pretrained", "laion2b_s34b_b79k")),
        device=str(clip_cfg.get("device", "auto")),
        prompts=prompts,
        keep_embedding=False,
    )

    # Seed dedup hashes from everything already kept OR rejected.
    hash_pool: List[np.ndarray] = []
    for d in (sleep_base, sleep_raw, base_root / "_rejected" / "sleep"):
        if d.is_dir():
            for p in d.iterdir():
                if p.suffix.lower() in IMAGE_EXTENSIONS:
                    im = cv2.imread(str(p))
                    if im is not None:
                        hash_pool.append(_ahash(im))
    log.info("Seeded %d perceptual hashes (kept + rejected) for dedup.", len(hash_pool))

    # Seed seen ids from manifest (provider+id) to skip known sources fast.
    seen_keys: set[str] = set()
    if manifest_csv.exists():
        with manifest_csv.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sid = row.get("source_id") or row.get("pexels_id") or ""
                prov = row.get("provider") or ("pexels" if row.get("pexels_id") else "")
                if sid:
                    seen_keys.add(f"{prov}:{sid}")

    start_index = _existing_max_index(sleep_base, sleep_raw) + 1
    next_index = start_index

    framer = _PoseFraming()
    manifest_rows: List[Dict[str, object]] = []
    kept = tried = rej_sleep = rej_frame = rej_small = rej_dup = rej_caption = 0

    log.info(
        "Wide sleep import | providers=%s target=%d start=%03d min_aspect=%.2f max_person_frac=%.2f",
        providers, target, start_index, min_aspect, max_person_frac,
    )

    with extractor:
        for prov in providers:
            if kept >= target:
                break
            search = _pexels if prov == "pexels" else _unsplash
            key = pk if prov == "pexels" else uk
            for query in DEFAULT_QUERIES:
                if kept >= target:
                    break
                for page in range(1, max_pages + 1):
                    if kept >= target:
                        break
                    try:
                        cands = search(key, query, page, per_page)
                    except Exception as e:
                        log.warning("%s search failed q=%r p=%d (%s)", prov, query, page, e)
                        break
                    if not cands:
                        break
                    time.sleep(sleep_sec)

                    for c in cands:
                        if kept >= target:
                            break
                        key_id = f"{c['provider']}:{c['id']}"
                        if key_id in seen_keys or not c["url"]:
                            continue
                        seen_keys.add(key_id)
                        tried += 1

                        cap_verdict = _caption_verdict(c["caption"])
                        if cap_verdict == "awake":
                            rej_caption += 1
                            continue
                        if require_sleep_caption and cap_verdict != "sleep":
                            rej_caption += 1
                            continue

                        data = _download(c["url"])
                        if not data:
                            continue
                        arr = np.frombuffer(data, np.uint8)
                        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if image is None:
                            continue
                        h, w = image.shape[:2]
                        if min(h, w) < min_short_side:
                            rej_small += 1
                            continue
                        if (w / max(1, h)) < min_aspect:
                            rej_frame += 1
                            continue

                        ah = _ahash(image)
                        if _is_dup(ah, hash_pool):
                            rej_dup += 1
                            continue

                        sims = extractor.extract(image).prompt_sim
                        good = float(sims[:ng].max())
                        bad = float(sims[ng:ng + nb].max())
                        wide = float(sims[i_wide0:i_wide1].max())
                        close = float(sims[i_close0:].max())
                        if not (good >= min_good and bad < good - margin):
                            rej_sleep += 1
                            continue
                        # framing: reject obvious close-ups
                        frac = framer.person_fraction(image)
                        if frac is not None and frac > max_person_frac:
                            rej_frame += 1
                            continue
                        if close > wide + framing_margin:
                            rej_frame += 1
                            continue

                        hash_pool.append(ah)
                        fname = f"{NAME_PREFIX}_{next_index:03d}.jpg"
                        if not dry_run:
                            okj, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                            if not okj:
                                continue
                            (sleep_base / fname).write_bytes(buf.tobytes())
                            (sleep_raw / fname).write_bytes(buf.tobytes())
                        desc = _ascii(c["caption"])[:140] or "a person asleep in a bedroom bed (wide shot)"
                        manifest_rows.append(
                            {
                                "filename": fname,
                                "source": f"{c['provider'].title()} (id={c['id']}, photographer={_ascii(str(c['author']))})",
                                "license": c["license"],
                                "description": desc,
                                "provider": c["provider"],
                                "source_id": c["id"],
                                "source_url": c["page"],
                            }
                        )
                        next_index += 1
                        kept += 1
                        if kept % 10 == 0 or kept <= 5:
                            log.info(
                                "+%d/%d %s [%s] good=%.3f bad=%.3f wide=%.3f close=%.3f frac=%s",
                                kept, target, fname, prov, good, bad, wide, close,
                                f"{frac:.2f}" if frac is not None else "na",
                            )
    framer.close()

    if manifest_rows and not dry_run:
        write_header = not manifest_csv.exists()
        fieldnames = ["filename", "source", "license", "description", "provider", "source_id", "source_url"]
        # If existing manifest has the old (pexels_*) schema, migrate it first.
        _ensure_manifest_schema(manifest_csv, fieldnames)
        with manifest_csv.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerows(manifest_rows)

    log.info("=" * 64)
    log.info(
        "DONE | kept=%d tried=%d rej_sleep=%d rej_frame=%d rej_caption=%d small=%d dup=%d",
        kept, tried, rej_sleep, rej_frame, rej_caption, rej_small, rej_dup,
    )
    log.info("Wrote %03d..%03d -> %s and %s", start_index, max(start_index, next_index - 1), sleep_base, sleep_raw)


def _ensure_manifest_schema(manifest_csv: Path, fieldnames: List[str]) -> None:
    """Migrate an older sleep_manifest.csv (pexels_id/pexels_url cols) in place."""
    if not manifest_csv.exists():
        return
    with manifest_csv.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows or set(fieldnames).issubset(rows[0].keys()):
        return
    migrated = []
    for r in rows:
        migrated.append(
            {
                "filename": r.get("filename", ""),
                "source": r.get("source", ""),
                "license": r.get("license", ""),
                "description": r.get("description", ""),
                "provider": r.get("provider") or ("pexels" if r.get("pexels_id") else ""),
                "source_id": r.get("source_id") or r.get("pexels_id", ""),
                "source_url": r.get("source_url") or r.get("pexels_url", ""),
            }
        )
    with manifest_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(migrated)


if __name__ == "__main__":
    app()
