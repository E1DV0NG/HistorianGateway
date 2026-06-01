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
    
    try:
        # POJISTKA: Bezpečné ověření metod přímo z objektu (ošetření interních typů v asyncua)
        if hasattr(status_code, "is_good") and callable(status_code.is_good):
            if status_code.is_good():
                return "Good"
        if hasattr(status_code, "is_bad") and callable(status_code.is_bad):
            if status_code.is_bad():
                return "Bad"
        
        # Záložní textové porovnání pro úvodní stavy a surové statusy
        text = str(status_code)
        if "Good" in text:
            return "Good"
        if "Bad" in text:
            return "Bad"
    except Exception:
        # Pokud cokoliv selže uvnitř knihovny (např. issubclass), vrátíme bezpečně Uncertain
        return "Uncertain"
        
    return "Uncertain"


class OpcUaSubscriptionHandler:
    def __init__(self, asset_id: int, source_id: str, event_bus: EventBus[SourceEvent]) -> None:
        self._asset_id = asset_id
        self._source_id = source_id
        self._event_bus = event_bus
        self._logger = logging.getLogger("ehistorian_gateway.opcua.handler")
        # Silná reference na běžící tasky, aby je nesežral Garbage Collector
        self._running_tasks: set[asyncio.Task[None]] = set()

    def datachange_notification(self, node: Any, val: Any, data: Any) -> None:
        loop = asyncio.get_running_loop()
        try:
            # POJISTKA: Pokud server poslal prázdnou nebo inicializační zprávu bez dat, ignorujeme ji
            if data is None:
                return

            # Načtení SourceTimestamp přímo z DataValue objektu
            source_timestamp = getattr(data, "SourceTimestamp", None)
            timestamp = source_timestamp or utcnow()
            
            if isinstance(timestamp, datetime) and timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            # Bezpečné získání StatusCode
            status_code = getattr(data, "StatusCode", None)
            quality = _to_quality_name(status_code)
            
            # Bezpečné získání stringu tagu
            node_id = getattr(node, "nodeid", None)
            tag = node_id.to_string() if node_id and hasattr(node_id, "to_string") else str(node)
            
            # Vytvoření eventu
            event = SourceEvent(
                asset_id=self._asset_id,
                source="opcua",
                source_id=self._source_id,
                tag=tag,
                value=val,
                timestamp=timestamp,
                quality=quality,
            )
            
            # Správa životního cyklu tasku (Fire-and-forget s držením reference)
            task = loop.create_task(self._event_bus.publish(event))
            self._running_tasks.add(task)
            task.add_done_callback(self._running_tasks.discard)
            
        except Exception as exc:
            self._logger.warning(
                "Failed to process OPC UA notification", 
                extra={"source_id": self._source_id, "error": str(exc)},
                exc_info=True # Přidá stack trace do logu pro snazší debugging
            )


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
        
        # Načtení node objektů ze stringových tagů
        nodes = [self._client.get_node(tag) for tag in self._tags]
        
        # Registrace odběru změn
        await self._subscription.subscribe_data_change(nodes)

    async def stop(self) -> None:
        if self._subscription is not None:
            try:
                await self._subscription.delete()
            except Exception:
                # Pokud mezitím spadlo spojení, delete() hodí chybu, kterou chceme ignorovat
                pass
            self._subscription = None