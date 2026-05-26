from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(slots=True)
class EventBusMetrics:
    published: int = 0
    dropped: int = 0
    high_water_mark: int = 0


class EventBus(Generic[T]):
    def __init__(self, maxsize: int) -> None:
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)
        self.metrics = EventBusMetrics()

    @property
    def size(self) -> int:
        return self._queue.qsize()

    async def publish(self, item: T) -> None:
        await self._queue.put(item)
        self.metrics.published += 1
        self.metrics.high_water_mark = max(self.metrics.high_water_mark, self._queue.qsize())

    async def get(self) -> T:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()