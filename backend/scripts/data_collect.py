"""Hackathon data collection workflow for RoomOS.

Commands::

    data_collect.py init      # create folder tree + checklist
    data_collect.py plan      # print 2h / 4h / 1-day schedules
    data_collect.py audit     # burst counts per class
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path

import typer

from roomos.config import load_config
from roomos.dataset.audit import images_needed_for_bursts
from roomos.utils.io import ensure_dir

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Hackathon data collection: folders, plans, audit.",
)

CLASSES = ("work", "sleep", "gaming", "relaxing", "away")

PLAN_2H = """
=== 2-hour plan (minimum viable personal demo) ===

Goal: train:images model that works on YOUR room for the judge live path.

0:00-0:10  npm run data:init && npm run data:plan
0:10-0:50  npm run data:capture-stills   (40 stills x 5 classes, ~8 min each)
0:50-0:55  npm run data:audit
0:55-1:25  npm run train:images && npm run train:verify
1:25-2:00  npm run demo — rehearse 5 poses on /live

Targets: 40 stills/class -> ~8 bursts (stride 5). Minimum is 30 stills (6 bursts).
Priority if short on time: work, sleep, away — then gaming, relaxing.
"""

PLAN_4H = """
=== 4-hour plan (solid hackathon accuracy) ===

Goal: balanced stills + a few dedicated video clips per mood.

0:00-0:15  init + audit empty tree
0:15-1:15  capture-stills @ 50/class (10 bursts/class)
1:15-1:45  Short videos: npm run capture per class (60-90s each)
           data/raw/work/desk.mp4, gaming/, sleep/, relaxing/, away/empty.mp4
1:45-2:00  audit
2:00-2:45  npm run train:videos  (or train:images if videos skipped)
2:45-3:15  train:verify + live rehearsal + 2-3 Teach-the-room corrections
3:15-4:00  Buffer: re-capture thin classes, second train pass

Targets: 50 stills/class OR 2 videos/class (60s+).
"""

PLAN_1D = """
=== 1-day plan (best realism without research scope) ===

Morning (quality stills):
  - 60-80 stills per class, 3 lighting passes (bright / normal / lamp)
  - Strict poses per CLASS_HINTS; avoid mixed labels in one folder

Midday (video supplements):
  - 3-5 clips per class (90s), whole-file label when one activity dominates
  - One mixed session: capture 5 min, label_windows.py for segments

Afternoon (balance + hard negatives):
  - Extra away (empty room, lights on/off, door open)
  - Extra work vs relaxing (easy confusion pair)
  - audit --target-bursts 20

Evening (train + validate):
  - train:images or merge features from multiple parquets (advanced)
  - train:verify, npm run demo, record which poses hit >60% confidence

Targets: 80+ stills/class OR 15+ bursts/class equivalent; 4+ videos/class optional.
Do NOT import 50k base images unless you need pretrain — fine-tune with YOUR room only.
"""


@app.command("init")
def cmd_init(
    base: Path = typer.Option(Path("data"), "--base"),
) -> None:
    """Create standard data/ layout (gitignored)."""
    dirs = [
        base / "raw_images" / c for c in CLASSES
    ] + [
        base / "raw" / c for c in CLASSES
    ] + [
        base / "labels",
        base / "features",
        base / "models" / "latest",
        base / "feedback",
        base / "logs",
    ]
    for d in dirs:
        ensure_dir(d)
    typer.echo(f"Created data tree under {base.resolve()}/")
    typer.echo("")
    typer.echo("Still images (fastest):  data/raw_images/<label>/*.jpg")
    typer.echo("Videos:               data/raw/<label>/*.mp4")
    typer.echo("")
    min_imgs = images_needed_for_bursts(6, 5, 5)
    good_imgs = images_needed_for_bursts(12, 5, 5)
    typer.echo(f"Sample counts (5-frame bursts, stride 5):")
    typer.echo(f"  minimum train:  {min_imgs} stills/class  (~6 bursts)")
    typer.echo(f"  good demo:      {good_imgs} stills/class (~12 bursts)  # 5 + 11*stride")
    typer.echo(f"  strong day:     80+ stills/class      (~16 bursts)")
    typer.echo("")
    typer.echo("Next: npm run data:capture-stills")


@app.command("plan")
def cmd_plan(
    which: str = typer.Option("all", "--which", help="2h | 4h | 1d | all"),
) -> None:
    """Print time-boxed collection schedules."""
    if which in ("2h", "all"):
        typer.echo(PLAN_2H.strip())
    if which in ("4h", "all"):
        typer.echo(PLAN_4H.strip())
    if which in ("1d", "all"):
        typer.echo(PLAN_1D.strip())


@app.command("audit")
def cmd_audit(
    images_dir: Path = typer.Option(Path("data/raw_images"), "--images-dir"),
    min_bursts: int = typer.Option(6, "--min-bursts"),
    target_bursts: int = typer.Option(12, "--target-bursts"),
) -> None:
    """Run dataset audit (exit 1 if any class below minimum)."""
    from scripts.audit_dataset import run_audit

    code = run_audit(
        images_dir,
        Path("data/raw"),
        Path("configs/train_personal.yaml"),
        min_bursts,
        target_bursts,
        5,
    )
    if code:
        raise typer.Exit(code=code)


if __name__ == "__main__":
    app()
