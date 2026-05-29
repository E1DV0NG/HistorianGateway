import asyncio
from datetime import datetime, timezone
import logging

class CircuitBreaker:
    """
    A simple Circuit Breaker.
    States:
    - CLOSED: Normal operation, requests are allowed.
    - OPEN: Requests fail fast.
    - HALF-OPEN: Allow one request to test if the underlying service is recovered.
    """
    def __init__(self, name: str, timeout_seconds: float = 30.0):
        self._name = name
        self._timeout_seconds = timeout_seconds
        self._state = "CLOSED"
        self._last_failure_time: datetime | None = None
        self._logger = logging.getLogger(f"ehistorian_gateway.circuit_breaker.{name}")
        self._lock = asyncio.Lock()

    async def can_execute(self) -> bool:
        async with self._lock:
            if self._state == "CLOSED":
                return True
            
            if self._state == "OPEN":
                assert self._last_failure_time is not None
                now = datetime.now(timezone.utc)
                if (now - self._last_failure_time).total_seconds() >= self._timeout_seconds:
                    self._state = "HALF-OPEN"
                    self._logger.info(f"CircuitBreaker '{self._name}' moved from OPEN to HALF-OPEN")
                    return True
                return False
                
            if self._state == "HALF-OPEN":
                # V HALF-OPEN propustime jen jeden testovaci request. Pokud se pta dalsi v ten samy cas, 
                # radsi ho odmítneme (čekáme na výsledek prvního).
                return False

        return False

    async def record_success(self) -> None:
        async with self._lock:
            if self._state != "CLOSED":
                self._state = "CLOSED"
                self._last_failure_time = None
                self._logger.info(f"CircuitBreaker '{self._name}' moved to CLOSED")

    async def record_failure(self) -> None:
        async with self._lock:
            self._last_failure_time = datetime.now(timezone.utc)
            if self._state != "OPEN":
                self._state = "OPEN"
                self._logger.warning(f"CircuitBreaker '{self._name}' moved to OPEN (timeout: {self._timeout_seconds}s)")
