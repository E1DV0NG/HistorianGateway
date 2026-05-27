from __future__ import annotations

import logging
from typing import Any

import aiohttp

from ehistorian_gateway.models.event import PersistedBatch


class RestClient:
    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds
        self._session: aiohttp.ClientSession | None = None
        self._logger = logging.getLogger("ehistorian_gateway.rest_client")

    async def start(self) -> None:
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def send_batch(self, api_url: str, batch: PersistedBatch) -> dict[str, Any]:
        if self._session is None:
            raise RuntimeError("HTTP session not started")

        endpoint = f"{str(api_url).rstrip('/')}/api/ehistorian/gateway/ingest"
        payload = {
            "gatewayId": batch.gateway_id,
            "events": [event.to_wire() for event in batch.events],
        }
        headers = {"Content-Type": "application/json", "X-Gateway-Batch-Id": batch.batch_id}

        async with self._session.post(endpoint, json=payload, headers=headers) as response:
            text = await response.text()
            if response.status >= 400:
                self._logger.warning(
                    "REST ingest failed",
                    extra={"status": response.status, "batch_id": batch.batch_id, "body": text[:1000]},
                )
                raise aiohttp.ClientResponseError(
                    response.request_info,
                    response.history,
                    status=response.status,
                    message=text,
                    headers=response.headers,
                )

            if not text:
                return {"status": response.status}

            return await response.json()