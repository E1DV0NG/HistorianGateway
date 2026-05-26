from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
from pathlib import Path

import aiohttp

from ehistorian_gateway.models.config import BootstrapConfig, GatewayConfig


ConfigCallback = Callable[[GatewayConfig], Awaitable[None]]


class ConfigManager:
    def __init__(self, bootstrap_path: str) -> None:
        self._bootstrap_path = Path(bootstrap_path)
        self._logger = logging.getLogger("ehistorian_gateway.config")
        self._bootstrap_config = self._load_bootstrap()
        self._current_config: GatewayConfig | None = None
        self._config_hash: str | None = None

    @property
    def bootstrap(self) -> BootstrapConfig:
        return self._bootstrap_config

    @property
    def current(self) -> GatewayConfig:
        if self._current_config is None:
            raise RuntimeError("Gateway configuration is not loaded")
        return self._current_config

    async def load_initial(self) -> GatewayConfig:
        remote = await self._try_fetch_remote_config()
        if remote is not None:
            self._set_current(remote)
            return remote

        local = self._load_local_gateway_config()
        self._set_current(local)
        self._logger.warning("Using local bootstrap config because remote config fetch failed")
        return local

    async def watch(self, stop_event: asyncio.Event, on_change: ConfigCallback) -> None:
        while not stop_event.is_set():
            refresh_seconds = self._current_config.config_refresh_seconds if self._current_config else 30.0
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=refresh_seconds)
                continue
            except asyncio.TimeoutError:
                pass

            remote = await self._try_fetch_remote_config()
            if remote is None:
                continue

            new_hash = self._hash_config(remote)
            if new_hash == self._config_hash:
                continue

            self._set_current(remote)
            self._logger.info("Gateway configuration changed", extra={"gateway_id": remote.gateway_id})
            await on_change(remote)

    async def _try_fetch_remote_config(self) -> GatewayConfig | None:
        endpoint = f"{str(self._bootstrap_config.api_url).rstrip('/')}/api/ehistorian/gateway/config/{self._bootstrap_config.gateway_id}"
        timeout = aiohttp.ClientTimeout(total=15)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(endpoint) as response:
                    if response.status >= 400:
                        body = await response.text()
                        self._logger.warning(
                            "Remote config fetch failed",
                            extra={"status": response.status, "body": body[:1000], "gateway_id": self._bootstrap_config.gateway_id},
                        )
                        return None
                    payload = await response.json()
                    return GatewayConfig.from_mapping(payload)
        except Exception as exc:
            self._logger.warning("Remote config fetch error", extra={"error": str(exc), "gateway_id": self._bootstrap_config.gateway_id})
            return None

    def _load_bootstrap(self) -> BootstrapConfig:
        payload = json.loads(self._bootstrap_path.read_text(encoding="utf-8"))
        return BootstrapConfig.model_validate(payload)

    def _load_local_gateway_config(self) -> GatewayConfig:
        payload = json.loads(self._bootstrap_path.read_text(encoding="utf-8"))
        return GatewayConfig.from_mapping(payload)

    def _set_current(self, config: GatewayConfig) -> None:
        self._current_config = config
        self._config_hash = self._hash_config(config)

    @staticmethod
    def _hash_config(config: GatewayConfig) -> str:
        return json.dumps(config.model_dump(mode="json", by_alias=True), sort_keys=True, separators=(",", ":"))