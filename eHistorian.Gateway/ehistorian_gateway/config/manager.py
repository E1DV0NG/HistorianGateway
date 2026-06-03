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
        import sys
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).resolve().parent
        else:
            base_dir = Path(__file__).resolve().parent.parent.parent
        cache_dir = base_dir / "cache"
        
        self._current_active_path = cache_dir / "current_active.json"
        self._history_dir = cache_dir / "config_history"
        self._latest_history_path = self._history_dir / "latest.json"
        self._bootstrap_config = self._load_bootstrap()
        self._current_config: GatewayConfig | None = None
        self._config_hash: str | None = None
        self._server_cb = None

    def set_server_circuit_breaker(self, cb) -> None:
        self._server_cb = cb

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
            self._save_current_active(remote)
            self._save_config_snapshot(remote)
            return remote

        active = self._load_current_active()
        if active is not None:
            self._set_current(active)
            self._logger.warning("Using current_active.json config (Last Known Good Config)")
            return active

        fallback = self._default_gateway_config()
        self._set_current(fallback)
        self._logger.warning("Using hardcoded safe default config")
        return fallback

    async def watch(self, stop_event: asyncio.Event, on_change: ConfigCallback) -> None:
        while not stop_event.is_set():
            try:
                # Use the configured refresh interval, fallback to 30s if not set
                refresh_interval = self._current_config.config_refresh_seconds if self._current_config else 30.0
                await asyncio.wait_for(stop_event.wait(), timeout=refresh_interval)
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
            self._save_current_active(remote)
            self._save_config_snapshot(remote)
            self._logger.info("Gateway configuration changed", extra={"gateway_id": remote.gateway_id})
            

            
            await on_change(remote)

    async def _try_fetch_remote_config(self) -> GatewayConfig | None:
        if self._server_cb is not None and not await self._server_cb.can_execute():
            self._logger.debug("Skipping config fetch because Server Circuit Breaker is OPEN")
            return None

        config_path = self._bootstrap_config.endpoints.config.replace("{gatewayId}", self._bootstrap_config.gateway_id)
        endpoint = f"{str(self._bootstrap_config.api_url).rstrip('/')}{config_path}"
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
                if self._server_cb is not None:
                    await self._server_cb.record_failure()
                return None
            payload = json.loads(body)
            if self._server_cb is not None:
                await self._server_cb.record_success()
            return GatewayConfig.from_mapping(payload)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', 'ignore')
            self._logger.warning(
                "Remote config fetch failed",
                extra={"status": exc.code, "body": body[:1000], "gateway_id": self._bootstrap_config.gateway_id},
            )
            if self._server_cb is not None:
                await self._server_cb.record_failure()
            return None
        except Exception as exc:
            self._logger.warning("Remote config fetch error", extra={"error": str(exc), "gateway_id": self._bootstrap_config.gateway_id})
            if self._server_cb is not None:
                await self._server_cb.record_failure()
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

    def _save_current_active(self, config: GatewayConfig) -> None:
        try:
            self._current_active_path.parent.mkdir(parents=True, exist_ok=True)
            payload = config.to_dict()
            self._current_active_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            self._logger.warning("Failed to save current active config", extra={"error": str(exc)})

    def _load_current_active(self) -> GatewayConfig | None:
        if self._current_active_path.exists():
            try:
                payload = json.loads(self._current_active_path.read_text(encoding="utf-8"))
                return GatewayConfig.from_mapping(payload)
            except Exception:
                self._logger.warning("Failed to read current_active.json, ignoring")
        return None


    def _save_config_snapshot(self, config: GatewayConfig) -> None:
        self._history_dir.mkdir(parents=True, exist_ok=True)
        payload = config.to_dict()
        payload["_snapshot_timestamp"] = datetime.now(timezone.utc).isoformat()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"config_{timestamp}.json"
        snapshot_path = self._history_dir / snapshot_name
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
            gateway_id="line-01-secret",
            api_url="http://localhost:5000",
            opcua=[],
            sql=[],
        )

    @staticmethod
    def _hash_config(config: GatewayConfig) -> str:
        return json.dumps(config.to_dict(), sort_keys=True, separators=(",", ":"))