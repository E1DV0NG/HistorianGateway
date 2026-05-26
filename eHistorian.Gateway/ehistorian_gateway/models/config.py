from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field


@dataclass
class OpcUaSourceConfig:
    asset_id: int
    url: str
    tags: list[str] = field(default_factory=list)
    sampling_ms: int = 1000

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OpcUaSourceConfig":
        return cls(
            asset_id=data["assetId"],
            url=data["url"],
            tags=data.get("tags", []),
            sampling_ms=data.get("samplingMs", 1000),
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
        )


@dataclass
class GatewayConfig:
    gateway_id: str
    api_url: str
    opcua: list[OpcUaSourceConfig] = field(default_factory=list)
    sql: list[SqlSourceConfig] = field(default_factory=list)

    batch_size: int = 500
    batch_flush_interval_seconds: float = 3.0
    config_refresh_seconds: float = 30.0
    queue_maxsize: int = 10000
    sqlite_path: str = "data/offline-buffer.db"
    request_timeout_seconds: float = 15.0
    retry_base_seconds: float = 1.0
    retry_max_seconds: float = 60.0
    health_host: str = "0.0.0.0"
    health_port: int = 8088

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "GatewayConfig":
        return cls(
            gateway_id=data["gatewayId"],
            api_url=str(data["apiUrl"]),
            opcua=[OpcUaSourceConfig.from_dict(d) for d in data.get("opcua", [])],
            sql=[SqlSourceConfig.from_dict(d) for d in data.get("sql", [])],
            batch_size=data.get("batchSize", 500),
            batch_flush_interval_seconds=data.get("batchFlushIntervalSeconds", 3.0),
            config_refresh_seconds=data.get("configRefreshSeconds", 30.0),
            queue_maxsize=data.get("queueMaxsize", 10000),
            sqlite_path=data.get("sqlitePath", "data/offline-buffer.db"),
            request_timeout_seconds=data.get("requestTimeoutSeconds", 15.0),
            retry_base_seconds=data.get("retryBaseSeconds", 1.0),
            retry_max_seconds=data.get("retryMaxSeconds", 60.0),
            health_host=data.get("healthHost", "0.0.0.0"),
            health_port=data.get("healthPort", 8088),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "gatewayId": self.gateway_id,
            "apiUrl": self.api_url,
            "opcua": [
                {
                    "assetId": o.asset_id,
                    "url": o.url,
                    "tags": o.tags,
                    "samplingMs": o.sampling_ms,
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
                } for s in self.sql
            ],
            "batchSize": self.batch_size,
            "batchFlushIntervalSeconds": self.batch_flush_interval_seconds,
            "configRefreshSeconds": self.config_refresh_seconds,
            "queueMaxsize": self.queue_maxsize,
            "sqlitePath": self.sqlite_path,
            "requestTimeoutSeconds": self.request_timeout_seconds,
            "retryBaseSeconds": self.retry_base_seconds,
            "retryMaxSeconds": self.retry_max_seconds,
            "healthHost": self.health_host,
            "healthPort": self.health_port,
        }


@dataclass
class BootstrapConfig:
    gateway_id: str
    api_url: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BootstrapConfig":
        return cls(
            gateway_id=data["gatewayId"],
            api_url=str(data["apiUrl"]),
        )
