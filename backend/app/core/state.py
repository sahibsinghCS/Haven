"""Process-wide application state.

We keep the long-running ML engine + a single broadcast hub here so any HTTP
route or WebSocket can read the latest snapshot without coupling to startup
order.
"""

from __future__ import annotations

import asyncio
from typing import Optional, Set

from roomos.config import load_config
from roomos.inference.live_pipeline import LiveInferenceEngine, LiveSnapshot, build_engine
from roomos.utils.logging import get_logger

from .config import settings

log = get_logger("roomos.app.state")


class SnapshotHub:
    """Async-aware fan-out of LiveSnapshot updates.

    The ML engine pushes synchronously from a background thread; we shuttle
    each update onto the asyncio loop so any number of WebSocket clients can
    subscribe via a queue.
    """

    def __init__(self) -> None:
        self._latest: Optional[LiveSnapshot] = None
        self._subscribers: Set[asyncio.Queue] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = asyncio.Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def latest(self) -> Optional[LiveSnapshot]:
        return self._latest

    def push_from_thread(self, snap: LiveSnapshot) -> None:
        """Called from the ML engine's background thread."""
        self._latest = snap
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._fanout, snap)

    def _fanout(self, snap: LiveSnapshot) -> None:
        """Push the newest snapshot; drop stale queued items (UI only needs latest)."""
        for q in list(self._subscribers):
            try:
                while not q.empty():
                    q.get_nowait()
                q.put_nowait(snap)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(snap)
                except Exception:
                    pass

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1)
        self._subscribers.add(q)
        if self._latest is not None:
            try:
                q.put_nowait(self._latest)
            except asyncio.QueueFull:
                pass
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)


class AppState:
    def __init__(self) -> None:
        self.engine: Optional[LiveInferenceEngine] = None
        self.engine_error: Optional[str] = None
        self.hub: SnapshotHub = SnapshotHub()

    # --- lifecycle -----------------------------------------------------

    def start_engine(self) -> dict:
        if self.engine is not None and self.engine.is_running():
            return {"status": "already_running"}
        try:
            cfg = load_config(settings.roomos_config)
            engine = build_engine(
                cfg,
                actions_config_path=settings.roomos_actions_config,
                on_snapshot=self.hub.push_from_thread,
            )
            engine.start_background()
            self.engine = engine
            self.engine_error = None
            return {"status": "started", "config": settings.roomos_config}
        except FileNotFoundError as e:
            self.engine_error = (
                f"Could not start engine: model bundle missing ({e}). "
                "Train a model first (see README)."
            )
            log.warning(self.engine_error)
            return {"status": "error", "error": self.engine_error}
        except Exception as e:
            self.engine_error = f"Engine start failed: {e!r}"
            log.exception("Engine start failed")
            return {"status": "error", "error": self.engine_error}

    def stop_engine(self) -> dict:
        if self.engine is None or not self.engine.is_running():
            return {"status": "not_running"}
        self.engine.stop()
        return {"status": "stopped"}


state = AppState()
