from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field


@dataclass
class EndpointsConfig:
    ingest: str = "/api/ehistorian/gateway/ingest"
    config: str = "/api/ehistorian/gateway/config/{gatewayId}"
    config_status: str = "/api/ehistorian/gateway/config-status"
    buffer_status: str = "/api/ehistorian/gateway/buffer-status"
    health_status: str = "/api/ehistorian/gateway/health-status"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EndpointsConfig":
        if not data:
            return cls()
        return cls(
            ingest=data.get("ingest", "/api/ehistorian/gateway/ingest"),
            config=data.get("config", "/api/ehistorian/gateway/config/{gatewayId}"),
            config_status=data.get("configStatus", "/api/ehistorian/gateway/config-status"),
            buffer_status=data.get("bufferStatus", "/api/ehistorian/gateway/buffer-status"),
            health_status=data.get("healthStatus", "/api/ehistorian/gateway/health-status"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ingest": self.ingest,
            "config": self.config,
            "configStatus": self.config_status,
            "bufferStatus": self.buffer_status,
            "healthStatus": self.health_status,
        }



@dataclass
class OpcUaSourceConfig:
    asset_id: int
    url: str
    tags: list[str] = field(default_factory=list)
    sampling_ms: int = 1000
    on_change: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OpcUaSourceConfig":
        return cls(
            asset_id=data["assetId"],
            url=data["url"],
            tags=data.get("tags", []),
            sampling_ms=data.get("samplingMs", 1000),
            on_change=data.get("onChange", 1),
        )


@dataclass
class SqlSourceConfig:
    asset_id: int
    connection_string: str
    table: str
    tag_column: str
    value_column: str
    timestamp_column: str | None = None
    polling_ms: int = 2000
    on_change: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SqlSourceConfig":
        return cls(
            asset_id=data["assetId"],
            connection_string=data["connectionString"],
            table=data["table"],
            tag_column=data["tagColumn"],
            value_column=data["valueColumn"],
            timestamp_column=data.get("timestampColumn"),
            polling_ms=data.get("pollingMs", 2000),
            on_change=data.get("onChange", 1),
        )


@dataclass
class GatewayConfig:
    gateway_id: str
    api_url: str
    endpoints: EndpointsConfig = field(default_factory=EndpointsConfig)
    opcua: list[OpcUaSourceConfig] = field(default_factory=list)
    sql: list[SqlSourceConfig] = field(default_factory=list)

    batch_size: int = 500
    batch_flush_interval_seconds: float = 3.0
    config_refresh_seconds: float = 30.0
    queue_maxsize: int = 10000
    sqlite_path: str = "data/offline-buffer.db"
    offline_buffer_max_bytes: int = 10 * 1024 * 1024
    request_timeout_seconds: float = 15.0
    retry_base_seconds: float = 1.0
    retry_max_seconds: float = 60.0
    health_host: str = "0.0.0.0"
    health_port: int = 8088
    send_logs: int = 0
    reset_error_count: int = 0

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "GatewayConfig":
        return cls(
            gateway_id=data["gatewayId"],
            api_url=str(data["apiUrl"]),
            endpoints=EndpointsConfig.from_dict(data.get("endpoints")),
            opcua=[OpcUaSourceConfig.from_dict(d) for d in data.get("opcua", [])],
            sql=[SqlSourceConfig.from_dict(d) for d in data.get("sql", [])],
            batch_size=data.get("batchSize", 500),
            batch_flush_interval_seconds=data.get("batchFlushIntervalSeconds", 3.0),
            config_refresh_seconds=data.get("configRefreshSeconds", 30.0),
            queue_maxsize=data.get("queueMaxsize", 10000),
            sqlite_path=data.get("sqlitePath", "data/offline-buffer.db"),
            offline_buffer_max_bytes=data.get("offlineBufferMaxBytes", 10 * 1024 * 1024),
            request_timeout_seconds=data.get("requestTimeoutSeconds", 15.0),
            retry_base_seconds=data.get("retryBaseSeconds", 1.0),
            retry_max_seconds=data.get("retryMaxSeconds", 60.0),
            health_host=data.get("healthHost", "0.0.0.0"),
            health_port=data.get("healthPort", 8088),
            send_logs=data.get("sendLogs", 0),
            reset_error_count=data.get("resetErrorCount", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "gatewayId": self.gateway_id,
            "apiUrl": self.api_url,
            "endpoints": self.endpoints.to_dict(),
            "opcua": [
                {
                    "assetId": o.asset_id,
                    "url": o.url,
                    "tags": o.tags,
                    "samplingMs": o.sampling_ms,
                    "onChange": o.on_change,
                } for o in self.opcua
            ],
            "sql": [
                {
                    "assetId": s.asset_id,
                    "connectionString": s.connection_string,
                    "table": s.table,
                    "tagColumn": s.tag_column,
                    "valueColumn": s.value_column,
                    "timestampColumn": s.timestamp_column,
                    "pollingMs": s.polling_ms,
                    "onChange": s.on_change,
                } for s in self.sql
            ],
            "batchSize": self.batch_size,
            "batchFlushIntervalSeconds": self.batch_flush_interval_seconds,
            "configRefreshSeconds": self.config_refresh_seconds,
            "queueMaxsize": self.queue_maxsize,
            "sqlitePath": self.sqlite_path,
            "offlineBufferMaxBytes": self.offline_buffer_max_bytes,
            "requestTimeoutSeconds": self.request_timeout_seconds,
            "retryBaseSeconds": self.retry_base_seconds,
            "retryMaxSeconds": self.retry_max_seconds,
            "healthHost": self.health_host,
            "healthPort": self.health_port,
            "sendLogs": self.send_logs,
            "resetErrorCount": self.reset_error_count,
        }


@dataclass
class BootstrapConfig:
    gateway_id: str
    api_url: str
    endpoints: EndpointsConfig = field(default_factory=EndpointsConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BootstrapConfig":
        return cls(
            gateway_id=data["gatewayId"],
            api_url=str(data["apiUrl"]),
            endpoints=EndpointsConfig.from_dict(data.get("endpoints")),
        )
