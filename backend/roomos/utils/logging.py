"""Logging helpers.

We funnel everything through ``logging`` so output is consistent across CLI
scripts, the live pipeline, and the FastAPI app. ``rich`` is used opportunistically
for nicer console output but the project does not require it at runtime.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional


_DEFAULT_FMT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"
_DEFAULT_DATEFMT = "%H:%M:%S"


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    use_rich: bool = True,
) -> None:
    """Configure root logging once.

    Calling this multiple times is safe — the second call is a no-op so library
    consumers can call it defensively without duplicating handlers.
    """
    root = logging.getLogger()
    if getattr(root, "_roomos_configured", False):
        return

    lvl = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(lvl)

    handlers: list[logging.Handler] = []

    if use_rich:
        try:
            from rich.logging import RichHandler

            handlers.append(
                RichHandler(
                    rich_tracebacks=True,
                    show_time=True,
                    show_level=True,
                    show_path=False,
                    markup=False,
                )
            )
        except Exception:
            use_rich = False

    if not use_rich:
        stream = logging.StreamHandler(stream=sys.stderr)
        stream.setFormatter(logging.Formatter(_DEFAULT_FMT, datefmt=_DEFAULT_DATEFMT))
        handlers.append(stream)

    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter(_DEFAULT_FMT, datefmt=_DEFAULT_DATEFMT))
        handlers.append(fh)

    for h in list(root.handlers):
        root.removeHandler(h)
    for h in handlers:
        root.addHandler(h)

    # Quiet a few chatty libraries we don't want in normal runs.
    for noisy in ("matplotlib", "PIL", "urllib3", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root._roomos_configured = True  # type: ignore[attr-defined]


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a namespaced logger and ensure logging is configured."""
    if not getattr(logging.getLogger(), "_roomos_configured", False):
        setup_logging(level=os.environ.get("ROOMOS_LOG_LEVEL", "INFO"))
    return logging.getLogger(name if name else "roomos")
