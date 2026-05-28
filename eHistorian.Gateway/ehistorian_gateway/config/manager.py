from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import urllib.request
import urllib.error

from ehistorian_gateway.models.config import BootstrapConfig, GatewayConfig


ConfigCallback = Callable[[GatewayConfig], Awaitable[None]]


class ConfigManager:
    def __init__(self, bootstrap_path: str) -> None:
        self._bootstrap_path = Path(bootstrap_path)
        self._logger = logging.getLogger("ehistorian_gateway.config")
        self._history_dir = self._bootstrap_path.parent / ".config_history"
        self._history_dir.mkdir(parents=True, exist_ok=True)
        self._latest_history_path = self._history_dir / "latest.json"
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
            self._save_config_snapshot(remote)
            return remote

        local_history = self._load_latest_history_config()
        if local_history is not None:
            self._set_current(local_history)
            self._logger.warning("Using last known local history config because remote config fetch failed")
            return local_history

        try:
            local = self._load_local_gateway_config()
            self._set_current(local)
            self._save_config_snapshot(local)
            self._logger.warning("Using local bootstrap config because remote config fetch failed")
            return local
        except Exception:
            fallback = self._default_gateway_config()
            self._set_current(fallback)
            self._logger.warning("Using safe default config because no local config or remote config is available")
            self._save_config_snapshot(fallback)
            return fallback

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
            self._save_config_snapshot(remote)
            self._logger.info("Gateway configuration changed", extra={"gateway_id": remote.gateway_id})
            await on_change(remote)

    async def _try_fetch_remote_config(self) -> GatewayConfig | None:
        endpoint = f"{str(self._bootstrap_config.api_url).rstrip('/')}/api/ehistorian/gateway/config/{self._bootstrap_config.gateway_id}"
        def fetch():
            req = urllib.request.Request(endpoint)
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read(), response.status
        try:
            body, status = await asyncio.to_thread(fetch)
            if status >= 400:
                self._logger.warning(
                    "Remote config fetch failed",
                    extra={"status": status, "body": body.decode('utf-8', 'ignore')[:1000], "gateway_id": self._bootstrap_config.gateway_id},
                )
                return None
            payload = json.loads(body)
            return GatewayConfig.from_mapping(payload)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', 'ignore')
            self._logger.warning(
                "Remote config fetch failed",
                extra={"status": exc.code, "body": body[:1000], "gateway_id": self._bootstrap_config.gateway_id},
            )
            return None
        except Exception as exc:
            self._logger.warning("Remote config fetch error", extra={"error": str(exc), "gateway_id": self._bootstrap_config.gateway_id})
            return None

    def _load_bootstrap(self) -> BootstrapConfig:
        try:
            payload = json.loads(self._bootstrap_path.read_text(encoding="utf-8"))
            return BootstrapConfig.from_dict(payload)
        except Exception:
            self._logger.warning("Bootstrap file missing or invalid, using safe defaults")
            return BootstrapConfig(gateway_id="unknown", api_url="http://localhost:5000")

    def _load_local_gateway_config(self) -> GatewayConfig:
        payload = json.loads(self._bootstrap_path.read_text(encoding="utf-8"))
        return GatewayConfig.from_mapping(payload)

    def _set_current(self, config: GatewayConfig) -> None:
        self._current_config = config
        self._config_hash = self._hash_config(config)

    def _load_latest_history_config(self) -> GatewayConfig | None:
        if self._latest_history_path.exists():
            try:
                payload = json.loads(self._latest_history_path.read_text(encoding="utf-8"))
                return GatewayConfig.from_mapping(payload)
            except Exception:
                self._logger.warning("Failed to read latest history config, ignoring")
                return None

        history_files = sorted(self._history_dir.glob("config_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in history_files:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                return GatewayConfig.from_mapping(payload)
            except Exception:
                continue
        return None

    def _save_config_snapshot(self, config: GatewayConfig) -> None:
        payload = config.to_dict()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot_path = self._history_dir / f"config_{timestamp}.json"
        try:
            snapshot_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            self._latest_history_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            self._prune_history_files(max_files=20)
        except Exception as exc:
            self._logger.warning("Failed to save config snapshot", extra={"error": str(exc)})

    def _prune_history_files(self, max_files: int = 20) -> None:
        history_files = sorted(self._history_dir.glob("config_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in history_files[max_files:]:
            try:
                path.unlink()
            except Exception:
                pass

    @staticmethod
    def _default_gateway_config() -> GatewayConfig:
        return GatewayConfig(
            gateway_id="unknown",
            api_url="http://localhost:5000",
            opcua=[],
            sql=[],
        )

    @staticmethod
    def _hash_config(config: GatewayConfig) -> str:
        return json.dumps(config.to_dict(), sort_keys=True, separators=(",", ":"))