"""45-second sliding-window buffer keyed on patient phone number."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class IngressPart:
    phone_number: str
    text: str = ""
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CompositePayload:
    phone_number: str
    text: str
    image_url: Optional[str]
    audio_url: Optional[str]
    parts: int
    window_started_at: datetime
    flushed_at: datetime


FlushCallback = Callable[[CompositePayload], Awaitable[None] | None]


class DebounceBuffer:
    def __init__(self, window_seconds: int = 45, on_flush: Optional[FlushCallback] = None) -> None:
        self.window_seconds = window_seconds
        self.on_flush = on_flush
        self._parts: dict[str, list[IngressPart]] = defaultdict(list)
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def add(self, part: IngressPart) -> None:
        async with self._lock:
            self._parts[part.phone_number].append(part)
            existing = self._tasks.get(part.phone_number)
            if existing and not existing.done():
                existing.cancel()
            self._tasks[part.phone_number] = asyncio.create_task(self._countdown(part.phone_number))

    async def _countdown(self, phone_number: str) -> None:
        try:
            await asyncio.sleep(self.window_seconds)
            await self.flush(phone_number)
        except asyncio.CancelledError:
            return

    async def flush(self, phone_number: str) -> Optional[CompositePayload]:
        async with self._lock:
            parts = self._parts.pop(phone_number, [])
            self._tasks.pop(phone_number, None)
        if not parts:
            return None
        texts = [p.text.strip() for p in parts if p.text and p.text.strip()]
        images = [p.image_url for p in parts if p.image_url]
        audios = [p.audio_url for p in parts if p.audio_url]
        payload = CompositePayload(
            phone_number=phone_number,
            text="\n".join(texts),
            image_url=images[-1] if images else None,
            audio_url=audios[-1] if audios else None,
            parts=len(parts),
            window_started_at=parts[0].received_at,
            flushed_at=datetime.now(timezone.utc),
        )
        logger.info("Debounce flush %s parts=%s", phone_number, payload.parts)
        if self.on_flush:
            result = self.on_flush(payload)
            if asyncio.iscoroutine(result):
                await result
        return payload

    def pending_count(self) -> int:
        return sum(len(v) for v in self._parts.values())
