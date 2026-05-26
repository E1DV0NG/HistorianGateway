from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass(slots=True)
class RetryPolicy:
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    factor: float = 2.0
    jitter_ratio: float = 0.2

    def compute_delay(self, attempt_number: int) -> float:
        raw = min(self.max_delay_seconds, self.base_delay_seconds * (self.factor ** max(0, attempt_number - 1)))
        jitter = raw * self.jitter_ratio * random.random()
        return raw + jitter