from __future__ import annotations

import asyncio
import logging

from asyncua import Client

from ehistorian_gateway.models.config import OpcUaSourceConfig
from ehistorian_gateway.opcua.subscription_manager import SubscriptionManager
from ehistorian_gateway.pipeline.event_bus import EventBus
from ehistorian_gateway.models.event import SourceEvent


class OpcUaSourceRunner:
    def __init__(self, source_id: str, config: OpcUaSourceConfig, event_bus: EventBus[SourceEvent], stop_event: asyncio.Event) -> None:
        self._source_id = source_id
        self._config = config
        self._event_bus = event_bus
        self._stop_event = stop_event
        self._logger = logging.getLogger("ehistorian_gateway.opcua")

    async def run(self) -> None:
        backoff = 1.0
        while not self._stop_event.is_set():
            client = Client(url=self._config.url)
            subscription_manager: SubscriptionManager | None = None
            try:
                await client.connect()
                subscription_manager = SubscriptionManager(
                    client=client,
                    asset_id=self._config.asset_id,
                    source_id=self._source_id,
                    sampling_ms=self._config.sampling_ms,
                    tags=self._config.tags,
                    event_bus=self._event_bus,
                )
                await subscription_manager.start()
                self._logger.info("Connected OPC UA source", extra={"source_id": self._source_id, "url": self._config.url})
                backoff = 1.0
                await self._stop_event.wait()
            except Exception as exc:
                self._logger.warning(
                    "OPC UA source disconnected",
                    extra={"source_id": self._source_id, "url": self._config.url, "error": str(exc), "backoff_seconds": backoff},
                )
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, 30.0)
            finally:
                if subscription_manager is not None:
                    try:
                        await subscription_manager.stop()
                    except Exception:
                        self._logger.debug("Ignoring OPC UA subscription shutdown error", extra={"source_id": self._source_id})
                try:
                    await client.disconnect()
                except Exception:
                    self._logger.debug("Ignoring OPC UA client disconnect error", extra={"source_id": self._source_id})