from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any

from ehistorian_gateway.models.event import SourceEvent, utcnow
from ehistorian_gateway.pipeline.event_bus import EventBus


def _to_quality_name(status_code: Any) -> str:
    if status_code is None:
        return "Uncertain"
    if hasattr(status_code, "is_good") and status_code.is_good():
        return "Good"
    if hasattr(status_code, "is_bad") and status_code.is_bad():
        return "Bad"
    text = str(status_code)
    if "Good" in text:
        return "Good"
    if "Bad" in text:
        return "Bad"
    return "Uncertain"


class OpcUaSubscriptionHandler:
    def __init__(self, asset_id: int, source_id: str, event_bus: EventBus[SourceEvent]) -> None:
        self._asset_id = asset_id
        self._source_id = source_id
        self._event_bus = event_bus
        self._logger = logging.getLogger("ehistorian_gateway.opcua.handler")

    def datachange_notification(self, node: Any, val: Any, data: Any) -> None:
        loop = asyncio.get_running_loop()
        try:
            monitored = getattr(data, "monitored_item", None)
            value_wrapper = getattr(monitored, "Value", None)
            source_timestamp = getattr(value_wrapper, "SourceTimestamp", None)
            timestamp = source_timestamp or utcnow()
            if isinstance(timestamp, datetime) and timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            status_code = getattr(value_wrapper, "StatusCode", None)
            quality = _to_quality_name(status_code)
            node_id = getattr(node, "nodeid", None)
            tag = node_id.to_string() if node_id is not None and hasattr(node_id, "to_string") else str(node)
            loop.create_task(
                self._event_bus.publish(
                    SourceEvent(
                        asset_id=self._asset_id,
                        source="opcua",
                        source_id=self._source_id,
                        tag=tag,
                        value=val,
                        timestamp=timestamp,
                        quality=quality,
                    )
                )
            )
        except Exception as exc:
            self._logger.warning("Failed to process OPC UA notification", extra={"source_id": self._source_id, "error": str(exc)})


class SubscriptionManager:
    def __init__(self, client: Any, asset_id: int, source_id: str, sampling_ms: int, tags: list[str], event_bus: EventBus[SourceEvent]) -> None:
        self._client = client
        self._asset_id = asset_id
        self._source_id = source_id
        self._sampling_ms = sampling_ms
        self._tags = tags
        self._event_bus = event_bus
        self._subscription: Any | None = None

    async def start(self) -> None:
        handler = OpcUaSubscriptionHandler(self._asset_id, self._source_id, self._event_bus)
        self._subscription = await self._client.create_subscription(self._sampling_ms, handler)
        nodes = [self._client.get_node(tag) for tag in self._tags]
        await self._subscription.subscribe_data_change(nodes)

    async def stop(self) -> None:
        if self._subscription is not None:
            await self._subscription.delete()
            self._subscription = None