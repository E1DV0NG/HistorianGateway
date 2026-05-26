from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class SourceEvent:
    asset_id: int
    source: str
    source_id: str
    tag: str
    value: Any
    timestamp: datetime
    quality: str = "Good"


@dataclass(slots=True)
class UnifiedEvent:
    gateway_id: str
    asset_id: int
    source: str
    source_id: str
    tag: str
    value: Any
    timestamp: datetime
    quality: str = "Good"

    def to_wire(self) -> dict[str, Any]:
        return {
            "gatewayId": self.gateway_id,
            "assetId": self.asset_id,
            "source": self.source,
            "sourceId": self.source_id,
            "tag": self.tag,
            "value": self.value,
            "timestamp": self.timestamp.astimezone(timezone.utc).isoformat(),
            "quality": self.quality,
        }


@dataclass(slots=True)
class PersistedBatch:
    batch_id: str
    gateway_id: str
    events: list[UnifiedEvent]
    attempts: int = 0

    @classmethod
    def from_events(cls, gateway_id: str, events: list[UnifiedEvent]) -> "PersistedBatch":
        serialized = json.dumps(
            [event.to_wire() for event in events],
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = sha256(f"{gateway_id}:{serialized}".encode("utf-8")).hexdigest()
        return cls(batch_id=digest, gateway_id=gateway_id, events=list(events), attempts=0)

    def payload_json(self) -> str:
        return json.dumps([event.to_wire() for event in self.events], separators=(",", ":"))

    @classmethod
    def from_payload(cls, batch_id: str, gateway_id: str, payload: str, attempts: int) -> "PersistedBatch":
        items = json.loads(payload)
        events = [
            UnifiedEvent(
                gateway_id=item["gatewayId"],
                asset_id=item["assetId"],
                source=item["source"],
                source_id=item["sourceId"],
                tag=item["tag"],
                value=item.get("value"),
                timestamp=datetime.fromisoformat(item["timestamp"]),
                quality=item.get("quality", "Good"),
            )
            for item in items
        ]
        return cls(batch_id=batch_id, gateway_id=gateway_id, events=events, attempts=attempts)