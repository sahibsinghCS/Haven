"""Broadcast feedback corrections (Telegram, web) to live UI subscribers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional, Set


@dataclass(frozen=True)
class FeedbackEvent:
    source: str  # telegram | web
    correction_id: str
    created_at: str
    predicted_label: str
    corrected_label: str
    confirmed: bool
    notes: str
    screenshot_count: int
    memory_examples: int
    auto_retrain_enabled: bool

    def to_frontend_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "correctionId": self.correction_id,
            "createdAt": self.created_at,
            "predictedLabel": self.predicted_label,
            "correctedLabel": self.corrected_label,
            "confirmed": self.confirmed,
            "notes": self.notes,
            "screenshotCount": self.screenshot_count,
            "memoryExamples": self.memory_examples,
            "autoRetrainEnabled": self.auto_retrain_enabled,
            "screenshotUrl": f"/api/live/feedback/screenshots/{self.correction_id}/frame.jpg",
        }


class FeedbackEventHub:
    """Thread-safe fan-out of correction events to WebSocket clients."""

    def __init__(self) -> None:
        self._latest: Optional[FeedbackEvent] = None
        self._subscribers: Set[asyncio.Queue] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def latest(self) -> Optional[FeedbackEvent]:
        return self._latest

    def publish_from_thread(self, event: FeedbackEvent) -> None:
        self._latest = event
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._fanout, event)

    def _fanout(self, event: FeedbackEvent) -> None:
        for q in list(self._subscribers):
            try:
                while not q.empty():
                    q.get_nowait()
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    pass

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=4)
        self._subscribers.add(q)
        if self._latest is not None:
            try:
                q.put_nowait(self._latest)
            except asyncio.QueueFull:
                pass
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)
