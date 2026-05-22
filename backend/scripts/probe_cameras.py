"""Probe local webcams across OpenCV capture backends.

Use this when the /live preview is black or stuck on "Camera starting".
It opens each webcam index 0..max_index with every backend supported on the
current OS, captures a frame, and reports mean luma so you can see which
combination actually produces image data.

From repo root::

    npm run probe:cameras
    npm run probe:cameras -- --max-index 6

Pick the (index, backend) combination with ok=true and mean_luma > ~20, then
either:

* set ``video.source`` and ``video.backend`` in ``backend/configs/default.yaml``
  (or your inference yaml), e.g.::

      video:
        source: 1
        backend: dshow

* or override at runtime::

      ROOMOS_VIDEO_SOURCE=1 ROOMOS_VIDEO_BACKEND=dshow npm run demo
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
import json
import sys

import typer

from roomos.video.input import probe_cameras

app = typer.Typer(add_completion=False, help="Probe local webcams.")


@app.command()
def main(
    max_index: int = typer.Option(4, "--max-index", "-n", min=0, max=15),
    json_out: bool = typer.Option(False, "--json", help="Emit raw JSON only."),
) -> None:
    results = probe_cameras(max_index=max_index)
    if json_out:
        typer.echo(json.dumps(results, indent=2))
        raise typer.Exit(code=0 if any(r["ok"] for r in results) else 1)

    dshow_names = sorted(
        {r["device_hint"] for r in results if r.get("device_hint")},
        key=str.lower,
    )
    if dshow_names:
        typer.echo("DirectShow devices (ffmpeg):")
        for i, name in enumerate(dshow_names):
            typer.echo(f"  [{i}] {name}")
        typer.echo("")

    typer.echo(f"Probed {len(results)} (index, backend) pairs on {sys.platform}:\n")
    header = f"{'idx':>3} {'backend':<18} {'ok':<3} {'luma':>7}  detail"
    typer.echo(header)
    typer.echo("-" * len(header))
    any_ok = False
    for r in results:
        ok = "yes" if r["ok"] else "no"
        luma = f"{r['mean_luma']:.1f}" if r.get("mean_luma") is not None else "  -  "
        if r["ok"]:
            hint = r.get("device_hint") or ""
            detail = f"shape={tuple(r.get('frame_shape') or ())}"
            if hint:
                detail += f"  ({hint})"
        else:
            detail = r.get("error") or ""
        typer.echo(f"{r['index']:>3} {r['backend']:<18} {ok:<3} {luma:>7}  {detail}")
        any_ok = any_ok or r["ok"]

    typer.echo("")
    if not any_ok:
        typer.secho(
            "No working camera found. Check Windows privacy settings "
            "(Settings → Privacy & security → Camera) and close other apps "
            "(Teams, Zoom, OBS) that may hold the device.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    bright = [r for r in results if r["ok"] and (r.get("mean_luma") or 0) >= 20]
    if not bright:
        typer.secho(
            "All openable cameras returned very dark frames (mean_luma < 20). "
            "Try a different backend, point the camera at a lit scene, or unplug "
            "and replug the device.",
            fg=typer.colors.YELLOW,
        )
    else:
        # Prefer DroidCam / non-integrated when multiple cameras are bright.
        def _score(row: dict) -> tuple:
            hint = (row.get("device_hint") or "").lower()
            droid = "droidcam" in hint
            integrated = "integrated" in hint or "facetime" in hint
            return (
                1 if droid else 0,
                0 if integrated else 1,
                row.get("mean_luma") or 0,
            )

        first = max(bright, key=_score)
        hint = first.get("device_hint") or "unknown device"
        typer.secho(
            f"Recommended:  source={first['index']}  backend={first['backend'].replace('CAP_', '').lower()}  ({hint})",
            fg=typer.colors.GREEN,
        )
        typer.echo(
            "Set backend/configs/inference.yaml:\n"
            f"  video:\n"
            f"    source: {first['index']}\n"
            f"    backend: {first['backend'].replace('CAP_', '').lower()}"
        )


if __name__ == "__main__":
    app()
