from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from ehistorian_gateway.models.config import GatewayConfig
from ehistorian_gateway.models.event import PersistedBatch, UnifiedEvent
from ehistorian_gateway.pipeline.event_bus import EventBus
from ehistorian_gateway.storage.sqlite_queue import SQLiteQueue


class Batcher:
    def __init__(
        self,
        source_bus: EventBus[UnifiedEvent],
        sqlite_queue: SQLiteQueue,
        config_provider: Callable[[], GatewayConfig],
    ) -> None:
        self._source_bus = source_bus
        self._sqlite_queue = sqlite_queue
        self._config_provider = config_provider
        self._logger = logging.getLogger("ehistorian_gateway.batcher")

    async def run(self, stop_event: asyncio.Event) -> None:
        buffer: list[UnifiedEvent] = []
        last_flush = asyncio.get_running_loop().time()

        while not stop_event.is_set():
            config = self._config_provider()
            timeout = max(0.1, config.batch_flush_interval_seconds - (asyncio.get_running_loop().time() - last_flush))

            try:
                item = await asyncio.wait_for(self._source_bus.get(), timeout=timeout)
            except asyncio.TimeoutError:
                if buffer:
                    await self._flush(buffer)
                    buffer.clear()
                    last_flush = asyncio.get_running_loop().time()
                continue

            try:
                buffer.append(item)
                if len(buffer) >= config.batch_size:
                    await self._flush(buffer)
                    buffer.clear()
                    last_flush = asyncio.get_running_loop().time()
            finally:
                self._source_bus.task_done()

        if buffer:
            await self._flush(buffer)

    async def _flush(self, events: list[UnifiedEvent]) -> None:
        batch = PersistedBatch.from_events(events[0].gateway_id, events)
        await self._sqlite_queue.enqueue_batch(batch)
        self._logger.info(
            "Persisted batch to sqlite queue",
            extra={"batch_id": batch.batch_id, "batch_size": len(events), "gateway_id": batch.gateway_id},
        )