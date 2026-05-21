"""Import public/base still images for RoomOS labels.

This script is intentionally conservative:

* downloads into data/base_images/<label>/, which is gitignored
* writes JSONL manifests with source/license metadata
* avoids overwriting files
* treats public data as weak labels for pretraining/bootstrap only

Best use:

    python scripts/import_base_images.py --target-total 50000
    python scripts/train_personal_images.py --images-dir data/base_images --min-bursts-per-class 20

Then fine-tune/replace with your own room images.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
import hashlib
import json
import os
import random
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

import typer
import yaml

from roomos.utils.io import append_jsonl, ensure_dir, write_json
from roomos.utils.logging import get_logger, setup_logging

app = typer.Typer(
    add_completion=False,
    help="Download/import public base images into ignored RoomOS label folders.",
)
log = get_logger("roomos.scripts.import_base_images")

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
ZENODO_RECORD_API = "https://zenodo.org/api/records/4453525"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_PROVIDERS = "zenodo,wikimedia,open_images"


@dataclass
class DownloadedImage:
    label: str
    path: Path
    provider: str
    source_url: str
    title: str = ""
    license: str = ""
    license_url: str = ""


@app.command()
def main(
    out_dir: Path = typer.Option(Path("data/base_images"), "--out-dir"),
    sources_config: Path = typer.Option(Path("configs/base_image_sources.yaml"), "--sources-config"),
    target_total: int = typer.Option(50_000, "--target-total"),
    per_class: int = typer.Option(0, "--per-class", help="0 means target_total / number of labels."),
    providers: str = typer.Option(DEFAULT_PROVIDERS, "--providers"),
    open_images_split: str = typer.Option("train", "--open-images-split"),
    seed: int = typer.Option(42, "--seed"),
    sleep_sec: float = typer.Option(0.2, "--sleep-sec", help="Delay between direct HTTP downloads."),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    random.seed(seed)
    cfg = _load_sources(sources_config)
    labels = list(cfg.keys())
    if not labels:
        raise typer.BadParameter(f"No roomos_labels found in {sources_config}")
    target_per_class = int(per_class or max(1, target_total // len(labels)))
    provider_list = [p.strip() for p in providers.split(",") if p.strip()]

    out_dir = ensure_dir(out_dir)
    manifest_dir = ensure_dir(out_dir / "_manifests")
    write_json(
        manifest_dir / "import_config.json",
        {
            "targetTotal": target_total,
            "targetPerClass": target_per_class,
            "providers": provider_list,
            "sourcesConfig": str(sources_config),
            "labels": labels,
        },
    )

    totals: Dict[str, int] = {label: _count_images(out_dir / label) for label in labels}
    for provider in provider_list:
        if all(count >= target_per_class for count in totals.values()):
            break
        log.info("Provider: %s", provider)
        if provider == "zenodo":
            _import_zenodo(cfg, out_dir, manifest_dir, totals, target_per_class, sleep_sec)
        elif provider == "wikimedia":
            _import_wikimedia(cfg, out_dir, manifest_dir, totals, target_per_class, sleep_sec)
        elif provider == "open_images":
            _import_open_images(
                cfg,
                out_dir,
                manifest_dir,
                totals,
                target_per_class,
                open_images_split,
                seed,
            )
        else:
            log.warning("Unknown provider %r; skipping", provider)

    write_json(manifest_dir / "summary.json", {"counts": totals, "targetPerClass": target_per_class})
    log.info("Import finished. Counts: %s", totals)
    missing = {label: target_per_class - count for label, count in totals.items() if count < target_per_class}
    if missing:
        log.warning(
            "Some labels are under target. Public sources may not have enough clean matches: %s",
            missing,
        )


def _import_zenodo(
    cfg: Dict[str, dict],
    out_dir: Path,
    manifest_dir: Path,
    totals: Dict[str, int],
    target_per_class: int,
    sleep_sec: float,
) -> None:
    data = _http_json(ZENODO_RECORD_API)
    files = data.get("files", [])
    if not isinstance(files, list):
        return

    for label, spec in cfg.items():
        if totals[label] >= target_per_class:
            continue
        terms = [t.lower() for t in spec.get("zenodo_activity_terms", [])]
        if not terms:
            continue
        for f in files:
            key = str(f.get("key", "")).lower()
            if not any(term in key for term in terms):
                continue
            url = f.get("links", {}).get("self")
            if not url:
                continue
            item = _download_url(
                label=label,
                provider="zenodo_human_activity",
                url=str(url),
                title=str(f.get("key", "")),
                out_dir=out_dir,
                manifest_dir=manifest_dir,
                license_name=str(data.get("metadata", {}).get("license", {}).get("id", "")),
            )
            if item is not None:
                totals[label] += 1
            if totals[label] >= target_per_class:
                break
            time.sleep(sleep_sec)


def _import_wikimedia(
    cfg: Dict[str, dict],
    out_dir: Path,
    manifest_dir: Path,
    totals: Dict[str, int],
    target_per_class: int,
    sleep_sec: float,
) -> None:
    for label, spec in cfg.items():
        if totals[label] >= target_per_class:
            continue
        categories = list(spec.get("wikimedia_categories", []))
        for category in categories:
            if totals[label] >= target_per_class:
                break
            for page in _commons_category_files(category, limit=max(50, target_per_class - totals[label])):
                info = _commons_file_info(page["title"])
                time.sleep(max(sleep_sec, 0.35))
                url = info.get("url")
                if not url:
                    continue
                item = _download_url(
                    label=label,
                    provider="wikimedia_commons",
                    url=url,
                    title=str(page["title"]),
                    out_dir=out_dir,
                    manifest_dir=manifest_dir,
                    license_name=str(info.get("license", "")),
                    license_url=str(info.get("license_url", "")),
                )
                if item is not None:
                    totals[label] += 1
                if totals[label] >= target_per_class:
                    break
                time.sleep(sleep_sec)


def _import_open_images(
    cfg: Dict[str, dict],
    out_dir: Path,
    manifest_dir: Path,
    totals: Dict[str, int],
    target_per_class: int,
    split: str,
    seed: int,
) -> None:
    try:
        import fiftyone.zoo as foz
    except Exception as e:
        log.warning(
            "Open Images import requires optional dependency 'fiftyone'. "
            "Install with: python -m pip install -r requirements-data.txt (%s)",
            e,
        )
        return

    for label, spec in cfg.items():
        need = target_per_class - totals[label]
        if need <= 0:
            continue
        classes = list(spec.get("open_images_classes", []))
        if not classes:
            continue
        log.info("Open Images: label=%s classes=%s need=%d", label, classes, need)
        dataset_name = f"roomos-open-images-v7-{split}-{label}-{seed}-{need}"
        try:
            dataset = foz.load_zoo_dataset(
                "open-images-v7",
                split=split,
                label_types=["detections", "classifications"],
                classes=classes,
                max_samples=need,
                shuffle=True,
                seed=seed,
                only_matching=False,
                dataset_name=dataset_name,
            )
        except Exception as e:
            log.warning("Open Images import failed for %s: %s", label, e)
            continue

        for sample in dataset:
            src = Path(sample.filepath)
            if not src.exists():
                continue
            dest = _copy_external_image(
                label=label,
                provider="open_images_v7",
                src=src,
                title=src.name,
                out_dir=out_dir,
                manifest_dir=manifest_dir,
                license_name="CC-BY-2.0 (Open Images image license; verify original image if publishing)",
            )
            if dest is not None:
                totals[label] += 1
            if totals[label] >= target_per_class:
                break


def _download_url(
    *,
    label: str,
    provider: str,
    url: str,
    title: str,
    out_dir: Path,
    manifest_dir: Path,
    license_name: str = "",
    license_url: str = "",
) -> Optional[DownloadedImage]:
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        suffix = ".jpg"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    dest_dir = ensure_dir(out_dir / label)
    dest = dest_dir / f"{provider}_{digest}{suffix}"
    if dest.exists():
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RoomOS dataset importer/0.1"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if len(data) < 1024:
            return None
        dest.write_bytes(data)
    except Exception as e:
        log.debug("Download failed %s: %s", url, e)
        return None
    item = DownloadedImage(label, dest, provider, url, title, license_name, license_url)
    _write_manifest(manifest_dir, item)
    return item


def _copy_external_image(
    *,
    label: str,
    provider: str,
    src: Path,
    title: str,
    out_dir: Path,
    manifest_dir: Path,
    license_name: str = "",
) -> Optional[Path]:
    digest = hashlib.sha1(str(src).encode("utf-8")).hexdigest()[:16]
    suffix = src.suffix.lower() if src.suffix.lower() in IMAGE_EXTENSIONS else ".jpg"
    dest = ensure_dir(out_dir / label) / f"{provider}_{digest}{suffix}"
    if dest.exists():
        return None
    try:
        shutil.copy2(src, dest)
    except Exception as e:
        log.debug("Copy failed %s: %s", src, e)
        return None
    _write_manifest(
        manifest_dir,
        DownloadedImage(
            label=label,
            path=dest,
            provider=provider,
            source_url=str(src),
            title=title,
            license=license_name,
        ),
    )
    return dest


def _commons_category_files(category: str, limit: int) -> Iterator[dict]:
    cmtitle = "Category:" + category.replace("Category:", "")
    params = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": cmtitle,
        "cmnamespace": "6",
        "cmlimit": str(min(500, max(1, limit))),
    }
    cont: Optional[str] = None
    yielded = 0
    while yielded < limit:
        q = dict(params)
        if cont:
            q["cmcontinue"] = cont
        try:
            data = _http_json(COMMONS_API + "?" + urllib.parse.urlencode(q))
        except urllib.error.HTTPError as e:
            log.warning("Wikimedia category query failed for %s: HTTP %s", category, e.code)
            return
        except Exception as e:
            log.warning("Wikimedia category query failed for %s: %s", category, e)
            return
        members = data.get("query", {}).get("categorymembers", [])
        if not members:
            return
        for m in members:
            yield m
            yielded += 1
            if yielded >= limit:
                return
        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            return


def _commons_file_info(title: str) -> dict:
    params = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "titles": title,
        "iiprop": "url|extmetadata",
        "iiurlwidth": "1024",
    }
    try:
        data = _http_json(COMMONS_API + "?" + urllib.parse.urlencode(params))
    except urllib.error.HTTPError as e:
        log.debug("Wikimedia file info failed for %s: HTTP %s", title, e.code)
        return {}
    except Exception as e:
        log.debug("Wikimedia file info failed for %s: %s", title, e)
        return {}
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        infos = page.get("imageinfo", [])
        if not infos:
            continue
        info = infos[0]
        meta = info.get("extmetadata", {})
        return {
            "url": info.get("thumburl") or info.get("url"),
            "license": _meta_value(meta, "LicenseShortName"),
            "license_url": _meta_value(meta, "LicenseUrl"),
        }
    return {}


def _meta_value(meta: dict, key: str) -> str:
    val = meta.get(key, {})
    if isinstance(val, dict):
        return str(val.get("value", ""))
    return str(val or "")


def _http_json(url: str, *, retries: int = 6) -> dict:
    """GET JSON with backoff on Wikimedia / API rate limits (HTTP 429)."""
    headers = {"User-Agent": "RoomOS/0.1 (local ML bootstrap; educational use)"}
    last_err: Optional[Exception] = None
    for attempt in range(max(1, retries)):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 503) and attempt < retries - 1:
                wait = min(60.0, (2.0**attempt) + random.uniform(0.5, 2.0))
                log.info("Rate limited (HTTP %s); retry in %.1fs", e.code, wait)
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(1.0 + attempt)
                continue
            raise
    raise RuntimeError(f"HTTP request failed after {retries} tries: {url}") from last_err


def _write_manifest(manifest_dir: Path, item: DownloadedImage) -> None:
    append_jsonl(
        manifest_dir / f"{item.label}.jsonl",
        {
            "label": item.label,
            "path": str(item.path),
            "provider": item.provider,
            "sourceUrl": item.source_url,
            "title": item.title,
            "license": item.license,
            "licenseUrl": item.license_url,
        },
    )


def _count_images(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _load_sources(path: Path) -> Dict[str, dict]:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    labels = raw.get("roomos_labels", {})
    if not isinstance(labels, dict):
        raise ValueError(f"{path} must contain a roomos_labels mapping")
    return labels


if __name__ == "__main__":
    app()
