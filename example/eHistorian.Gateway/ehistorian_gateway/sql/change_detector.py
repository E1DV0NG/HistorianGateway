from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ChangeDetector:
    _state: dict[str, tuple[str, str | None]] = field(default_factory=dict)

    def has_changed(self, tag: str, value: Any, timestamp: datetime | None) -> bool:
        signature = (repr(value), timestamp.isoformat() if timestamp else None)
        previous = self._state.get(tag)
        if previous == signature:
            return False
        self._state[tag] = signature
        return True