from __future__ import annotations

import asyncio
from datetime import timezone
import logging

from ehistorian_gateway.models.config import SqlSourceConfig
from ehistorian_gateway.models.event import SourceEvent, utcnow
from ehistorian_gateway.pipeline.event_bus import EventBus
from ehistorian_gateway.sql.change_detector import ChangeDetector
from ehistorian_gateway.sql.sql_client import SqlClient
from ehistorian_gateway.utils.circuit_breaker import CircuitBreaker


class SqlPoller:
    def __init__(self, source_id: str, config: SqlSourceConfig, event_bus: EventBus[SourceEvent], stop_event: asyncio.Event, polling_allowed: asyncio.Event) -> None:
        self._source_id = source_id
        self._config = config
        self._event_bus = event_bus
        self._stop_event = stop_event
        self._polling_allowed = polling_allowed
        self._client = SqlClient(config)
        self._change_detector = ChangeDetector()
        self._circuit_breaker = CircuitBreaker(f"sql_poller_{source_id}", timeout_seconds=30.0)
        self._logger = logging.getLogger("ehistorian_gateway.sql_poller")

    async def run(self) -> None:
        while not self._stop_event.is_set():
            if not await self._circuit_breaker.can_execute():
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                continue

            try:
                # Backpressure: wait until polling is allowed (under 10MB limit)
                await self._polling_allowed.wait()
                if self._stop_event.is_set():
                    break

                rows = await self._client.read_snapshot()
                for row in rows:
                    timestamp = row["timestamp"] or utcnow()
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    changed = self._change_detector.has_changed(row["tag"], row["value"], timestamp)
                    if self._config.on_change != 0 and not changed:
                        continue
                    await self._event_bus.publish(
                        SourceEvent(
                            asset_id=self._config.asset_id,
                            source="sql",
                            source_id=self._source_id,
                            tag=row["tag"],
                            value=row["value"],
                            timestamp=timestamp,
                            quality="Good",
                        )
                    )
                await self._circuit_breaker.record_success()
                
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=max(0.2, self._config.polling_ms / 1000.0))
                except asyncio.TimeoutError:
                    pass
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                self._logger.warning(
                    "SQL poller iteration failed",
                    extra={"source_id": self._source_id, "error": str(exc)},
                )
                await self._circuit_breaker.record_failure()