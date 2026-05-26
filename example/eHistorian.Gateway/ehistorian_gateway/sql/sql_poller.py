from __future__ import annotations

import asyncio
from datetime import timezone
import logging

from ehistorian_gateway.models.config import SqlSourceConfig
from ehistorian_gateway.models.event import SourceEvent, utcnow
from ehistorian_gateway.pipeline.event_bus import EventBus
from ehistorian_gateway.sql.change_detector import ChangeDetector
from ehistorian_gateway.sql.sql_client import SqlClient


class SqlPoller:
    def __init__(self, source_id: str, config: SqlSourceConfig, event_bus: EventBus[SourceEvent], stop_event: asyncio.Event) -> None:
        self._source_id = source_id
        self._config = config
        self._event_bus = event_bus
        self._stop_event = stop_event
        self._client = SqlClient(config)
        self._change_detector = ChangeDetector()
        self._logger = logging.getLogger("ehistorian_gateway.sql_poller")

    async def run(self) -> None:
        backoff = 1.0
        while not self._stop_event.is_set():
            try:
                rows = await self._client.read_snapshot()
                for row in rows:
                    timestamp = row["timestamp"] or utcnow()
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    if not self._change_detector.has_changed(row["tag"], row["value"], timestamp):
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
                backoff = 1.0
                await asyncio.wait_for(self._stop_event.wait(), timeout=max(0.2, self._config.polling_ms / 1000.0))
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                self._logger.warning(
                    "SQL poller iteration failed",
                    extra={"source_id": self._source_id, "error": str(exc), "backoff_seconds": backoff},
                )
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, 30.0)