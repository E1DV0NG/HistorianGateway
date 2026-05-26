from __future__ import annotations

import asyncio
import logging
from typing import Callable

from ehistorian_gateway.models.event import SourceEvent, UnifiedEvent
from ehistorian_gateway.pipeline.event_bus import EventBus


class Normalizer:
    def __init__(
        self,
        source_bus: EventBus[SourceEvent],
        target_bus: EventBus[UnifiedEvent],
        gateway_id_provider: Callable[[], str],
    ) -> None:
        self._source_bus = source_bus
        self._target_bus = target_bus
        self._gateway_id_provider = gateway_id_provider
        self._logger = logging.getLogger("ehistorian_gateway.normalizer")

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                source_event = await asyncio.wait_for(self._source_bus.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            try:
                quality = source_event.quality if source_event.quality in {"Good", "Bad", "Uncertain"} else "Uncertain"
                unified = UnifiedEvent(
                    gateway_id=self._gateway_id_provider(),
                    asset_id=source_event.asset_id,
                    source=source_event.source,
                    source_id=source_event.source_id,
                    tag=source_event.tag,
                    value=source_event.value,
                    timestamp=source_event.timestamp,
                    quality=quality,
                )
                await self._target_bus.publish(unified)
            finally:
                self._source_bus.task_done()

            self._logger.debug("Normalized event", extra={"tag": unified.tag, "source": unified.source})