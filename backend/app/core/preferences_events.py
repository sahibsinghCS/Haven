"""Broadcast preference updates (Telegram, web) to UI subscribers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, List, Optional, Set


@dataclass(frozen=True)
class PreferencesEvent:
    source: str
    updated_at: str
    active_preset_id: str
    preset_name: str
    target_states: List[str]
    changes: List[str]
    notes: str

    def to_frontend_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "updatedAt": self.updated_at,
            "activePresetId": self.active_preset_id,
            "presetName": self.preset_name,
            "targetStates": self.target_states,
            "changes": self.changes,
            "notes": self.notes,
        }


class PreferencesEventHub:
    def __init__(self) -> None:
        self._latest: Optional[PreferencesEvent] = None
        self._subscribers: Set[asyncio.Queue] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def latest(self) -> Optional[PreferencesEvent]:
        return self._latest

    def publish_from_thread(self, event: PreferencesEvent) -> None:
        self._latest = event
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._fanout, event)

    def _fanout(self, event: PreferencesEvent) -> None:
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
