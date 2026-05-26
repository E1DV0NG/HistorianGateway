from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class OpcUaSourceConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    asset_id: int = Field(alias="assetId")
    url: str
    tags: list[str] = Field(default_factory=list)
    sampling_ms: int = Field(default=1000, alias="samplingMs")


class SqlSourceConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    asset_id: int = Field(alias="assetId")
    connection_string: str = Field(alias="connectionString")
    table: str
    tag_column: str = Field(alias="tagColumn")
    value_column: str = Field(alias="valueColumn")
    timestamp_column: str | None = Field(default=None, alias="timestampColumn")
    polling_ms: int = Field(default=2000, alias="pollingMs")


class GatewayConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    gateway_id: str = Field(alias="gatewayId")
    api_url: HttpUrl | str = Field(alias="apiUrl")
    opcua: list[OpcUaSourceConfig] = Field(default_factory=list)
    sql: list[SqlSourceConfig] = Field(default_factory=list)

    batch_size: int = Field(default=500, alias="batchSize")
    batch_flush_interval_seconds: float = Field(default=3.0, alias="batchFlushIntervalSeconds")
    config_refresh_seconds: float = Field(default=30.0, alias="configRefreshSeconds")
    queue_maxsize: int = Field(default=10000, alias="queueMaxsize")
    sqlite_path: str = Field(default="data/offline-buffer.db", alias="sqlitePath")
    request_timeout_seconds: float = Field(default=15.0, alias="requestTimeoutSeconds")
    retry_base_seconds: float = Field(default=1.0, alias="retryBaseSeconds")
    retry_max_seconds: float = Field(default=60.0, alias="retryMaxSeconds")
    health_host: str = Field(default="0.0.0.0", alias="healthHost")
    health_port: int = Field(default=8088, alias="healthPort")

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "GatewayConfig":
        return cls.model_validate(payload)


class BootstrapConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    gateway_id: str = Field(alias="gatewayId")
    api_url: HttpUrl | str = Field(alias="apiUrl")
