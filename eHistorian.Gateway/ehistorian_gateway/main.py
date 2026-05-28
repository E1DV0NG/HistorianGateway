from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
import signal

from ehistorian_gateway.config.manager import ConfigManager
from ehistorian_gateway.models.config import GatewayConfig
from ehistorian_gateway.models.event import PersistedBatch, SourceEvent, UnifiedEvent
from ehistorian_gateway.opcua.client import OpcUaSourceRunner
from ehistorian_gateway.pipeline.batcher import Batcher
from ehistorian_gateway.pipeline.event_bus import EventBus
from ehistorian_gateway.pipeline.normalizer import Normalizer
from ehistorian_gateway.sender.rest_client import RestClient
from ehistorian_gateway.sender.retry import RetryPolicy
from ehistorian_gateway.sql.sql_poller import SqlPoller
from ehistorian_gateway.storage.sqlite_queue import SQLiteQueue
from ehistorian_gateway.utils.logging import configure_logging


@dataclass(slots=True)
class RuntimeMetrics:
    retry_count: int = 0
    last_successful_send_at: str | None = None
    last_config_refresh_at: str | None = None


@dataclass(slots=True)
class CollectorHandle:
    task: asyncio.Task[None]
    stop_event: asyncio.Event


class GatewayApplication:
    def __init__(self, bootstrap_path: str) -> None:
        self._logger = logging.getLogger("ehistorian_gateway.app")
        self._config_manager = ConfigManager(bootstrap_path)
        self._source_bus: EventBus[SourceEvent] | None = None
        self._normalized_bus: EventBus[UnifiedEvent] | None = None
        self._sqlite_queue: SQLiteQueue | None = None
        self._rest_client: RestClient | None = None
        self._retry_policy: RetryPolicy | None = None
        self._config: GatewayConfig | None = None
        self._metrics = RuntimeMetrics()
        self._stop_event = asyncio.Event()
        self._collector_handles: list[CollectorHandle] = []
        self._config_lock = asyncio.Lock()
        self._background_tasks: list[asyncio.Task[None]] = []

    async def run(self) -> None:
        initial_config = await self._config_manager.load_initial()
        self._metrics.last_config_refresh_at = datetime.now(timezone.utc).isoformat()
        self._apply_config(initial_config)
        await self._start_runtime()

        loop = asyncio.get_running_loop()
        for signame in ("SIGINT", "SIGTERM"):
            if hasattr(signal, signame):
                with suppress(NotImplementedError):
                    loop.add_signal_handler(getattr(signal, signame), self._stop_event.set)

        async with asyncio.TaskGroup() as task_group:
            task_group.create_task(self._config_manager.watch(self._stop_event, self._handle_config_change))
            task_group.create_task(self._run_health_server())
            task_group.create_task(self._wait_for_stop())
            for task in self._background_tasks:
                task_group.create_task(self._await_background(task))

    async def _start_runtime(self) -> None:
        assert self._config is not None
        self._source_bus = EventBus(maxsize=self._config.queue_maxsize)
        self._normalized_bus = EventBus(maxsize=self._config.queue_maxsize)
        sqlite_path = os.getenv("EHG_SQLITE_PATH") or os.getenv("EMG_SQLITE_PATH") or self._config.sqlite_path
        self._sqlite_queue = SQLiteQueue(sqlite_path, max_bytes=self.current_config.offline_buffer_max_bytes)
        await self._sqlite_queue.initialize()
        self._rest_client = RestClient(timeout_seconds=self._config.request_timeout_seconds)
        await self._rest_client.start()
        self._retry_policy = RetryPolicy(
            base_delay_seconds=self._config.retry_base_seconds,
            max_delay_seconds=self._config.retry_max_seconds,
        )
        normalizer = Normalizer(self._source_bus, self._normalized_bus, lambda: self.current_config.gateway_id)
        batcher = Batcher(self._normalized_bus, self._sqlite_queue, lambda: self.current_config)
        self._background_tasks = [
            asyncio.create_task(normalizer.run(self._stop_event)),
            asyncio.create_task(batcher.run(self._stop_event)),
            asyncio.create_task(self._sender_loop()),
        ]
        await self._restart_collectors(self.current_config)

    @property
    def current_config(self) -> GatewayConfig:
        if self._config is None:
            raise RuntimeError("Gateway config not loaded")
        return self._config

    def _apply_config(self, config: GatewayConfig) -> None:
        self._config = config

    async def _handle_config_change(self, config: GatewayConfig) -> None:
        async with self._config_lock:
            self._apply_config(config)
            self._metrics.last_config_refresh_at = datetime.now(timezone.utc).isoformat()
            await self._restart_collectors(config)

    async def _restart_collectors(self, config: GatewayConfig) -> None:
        await self._stop_collectors()
        if self._source_bus is None:
            return

        handles: list[CollectorHandle] = []
        for index, opcua_config in enumerate(config.opcua):
            stop_event = asyncio.Event()
            runner = OpcUaSourceRunner(f"opcua-{index}:asset-{opcua_config.asset_id}", opcua_config, self._source_bus, stop_event)
            handles.append(CollectorHandle(asyncio.create_task(runner.run()), stop_event))

        for index, sql_config in enumerate(config.sql):
            stop_event = asyncio.Event()
            poller = SqlPoller(f"sql-{index}:asset-{sql_config.asset_id}:{sql_config.table}", sql_config, self._source_bus, stop_event)
            handles.append(CollectorHandle(asyncio.create_task(poller.run()), stop_event))

        self._collector_handles = handles
        self._logger.info(
            "Collectors started",
            extra={"gateway_id": config.gateway_id, "opcua_sources": len(config.opcua), "sql_sources": len(config.sql)},
        )

    async def _stop_collectors(self) -> None:
        if not self._collector_handles:
            return

        for handle in self._collector_handles:
            handle.stop_event.set()
        for handle in self._collector_handles:
            handle.task.cancel()
        for handle in self._collector_handles:
            with suppress(asyncio.CancelledError, Exception):
                await handle.task
        self._collector_handles.clear()

    async def _sender_loop(self) -> None:
        assert self._sqlite_queue is not None
        assert self._rest_client is not None
        assert self._retry_policy is not None

        while not self._stop_event.is_set():
            batch = await self._sqlite_queue.lease_next_batch()
            if batch is None:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                continue

            try:
                await self._rest_client.send_batch(str(self.current_config.api_url), batch)
                await self._sqlite_queue.mark_sent(batch.batch_id)
                self._metrics.last_successful_send_at = datetime.now(timezone.utc).isoformat()
                self._logger.info(
                    "Batch delivered",
                    extra={"batch_id": batch.batch_id, "batch_size": len(batch.events), "gateway_id": batch.gateway_id},
                )
            except Exception as exc:
                self._metrics.retry_count += 1
                delay = self._retry_policy.compute_delay(batch.attempts + 1)
                await self._sqlite_queue.mark_retry(batch.batch_id, str(exc), delay)
                self._logger.warning(
                    "Batch delivery failed; scheduled retry",
                    extra={
                        "batch_id": batch.batch_id,
                        "attempt": batch.attempts + 1,
                        "delay_seconds": delay,
                        "error": str(exc),
                    },
                )

    async def _run_health_server(self) -> None:
        async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                request_line = await reader.readline()
                if not request_line:
                    return
                while True:
                    line = await reader.readline()
                    if line == b'\r\n' or not line:
                        break
                
                if request_line.startswith(b"GET /health "):
                    pending_batches = await self._sqlite_queue.pending_count() if self._sqlite_queue is not None else 0
                    queue_size = self._source_bus.size if self._source_bus is not None else 0
                    normalized_queue_size = self._normalized_bus.size if self._normalized_bus is not None else 0
                    payload = {
                        "status": "healthy" if not self._stop_event.is_set() else "stopping",
                        "gatewayId": self.current_config.gateway_id,
                        "queueSize": queue_size,
                        "normalizedQueueSize": normalized_queue_size,
                        "retryCount": self._metrics.retry_count,
                        "droppedEvents": self._source_bus.metrics.dropped if self._source_bus is not None else 0,
                        "pendingBatches": pending_batches,
                        "lastSuccessfulSendAt": self._metrics.last_successful_send_at,
                        "lastConfigRefreshAt": self._metrics.last_config_refresh_at,
                        "collectors": len(self._collector_handles),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    import json
                    body = json.dumps(payload).encode('utf-8')
                    headers = (
                        b"HTTP/1.1 200 OK\r\n"
                        b"Content-Type: application/json\r\n"
                        + f"Content-Length: {len(body)}\r\n".encode('ascii')
                        + b"Connection: close\r\n\r\n"
                    )
                    writer.write(headers + body)
                    await writer.drain()
                else:
                    writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                    await writer.drain()
            except Exception:
                pass
            finally:
                writer.close()
                with suppress(Exception):
                    await writer.wait_closed()

        server = await asyncio.start_server(handle_client, self.current_config.health_host, self.current_config.health_port)
        self._logger.info(
            "Health endpoint started",
            extra={"host": self.current_config.health_host, "port": self.current_config.health_port},
        )
        async with server:
            await self._stop_event.wait()

    async def _wait_for_stop(self) -> None:
        await self._stop_event.wait()
        await self.shutdown()

    async def shutdown(self) -> None:
        await self._stop_collectors()
        for task in self._background_tasks:
            task.cancel()
        for task in self._background_tasks:
            with suppress(asyncio.CancelledError, Exception):
                await task
        if self._rest_client is not None:
            await self._rest_client.close()

    async def _await_background(self, task: asyncio.Task[None]) -> None:
        await task


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="eHistorian Gateway")
    parser.add_argument(
        "--bootstrap",
        default=os.getenv("EHG_BOOTSTRAP_CONFIG") or os.getenv("EMG_BOOTSTRAP_CONFIG") or "example.config.json",
        help="Path to the local bootstrap JSON config.",
    )
    return parser.parse_args()


async def async_main() -> None:
    configure_logging()
    args = parse_args()
    app = GatewayApplication(args.bootstrap)
    await app.run()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()