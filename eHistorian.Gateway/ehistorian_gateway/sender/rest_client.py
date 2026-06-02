from __future__ import annotations

import logging
from typing import Any

import urllib.request
import urllib.error
import json
import asyncio

from ehistorian_gateway.models.event import PersistedBatch


class RestClient:
    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds
        self._started = False
        self._logger = logging.getLogger("ehistorian_gateway.rest_client")

    async def start(self) -> None:
        self._started = True

    async def close(self) -> None:
        self._started = False

    async def send_batch(self, endpoint: str, batch: PersistedBatch) -> dict[str, Any]:
        if not self._started:
            raise RuntimeError("HTTP session not started")
        payload = {
            "gatewayId": batch.gateway_id,
            "events": [event.to_wire() for event in batch.events],
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "X-Gateway-Batch-Id": str(batch.batch_id)}

        def fetch():
            req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self._timeout_seconds) as response:
                return response.read(), response.status

        try:
            body, status = await asyncio.to_thread(fetch)
            if not body:
                return {"status": status}
            return json.loads(body)
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "ignore")
            self._logger.warning(
                "REST ingest failed",
                extra={"status": exc.code, "batch_id": batch.batch_id, "body": text[:1000]},
            )
            raise RuntimeError(f"HTTP {exc.code}: {text}")
        except Exception as exc:
            raise RuntimeError(f"Request failed: {exc}")