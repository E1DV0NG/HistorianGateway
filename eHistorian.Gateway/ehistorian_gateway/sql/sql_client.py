from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import re
from typing import Any

import pyodbc

from ehistorian_gateway.models.config import SqlSourceConfig


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SqlClient:
    def __init__(self, config: SqlSourceConfig) -> None:
        self._config = config
        self._validate_identifier(config.table)
        self._validate_identifier(config.tag_column)
        self._validate_identifier(config.value_column)
        if config.timestamp_column:
            self._validate_identifier(config.timestamp_column)

    async def read_snapshot(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._read_snapshot_sync)

    def _read_snapshot_sync(self) -> list[dict[str, Any]]:
        timestamp_projection = (
            f", [{self._config.timestamp_column}] AS snapshot_timestamp"
            if self._config.timestamp_column
            else ""
        )
        query = (
            f"SELECT [{self._config.tag_column}] AS tag_name, [{self._config.value_column}] AS value{timestamp_projection} "
            f"FROM [{self._config.table}]"
        )

        with pyodbc.connect(self._config.connection_string, timeout=5) as connection:
            cursor = connection.cursor()
            rows = cursor.execute(query).fetchall()
            records: list[dict[str, Any]] = []
            for row in rows:
                timestamp = getattr(row, "snapshot_timestamp", None)
                if isinstance(timestamp, datetime):
                    timestamp = timestamp.astimezone(timezone.utc) if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
                records.append(
                    {
                        "tag": str(row.tag_name),
                        "value": row.value,
                        "timestamp": timestamp,
                    }
                )
            return records

    @staticmethod
    def _validate_identifier(identifier: str) -> None:
        if not IDENTIFIER_PATTERN.match(identifier):
            raise ValueError(f"Unsupported SQL identifier '{identifier}'. Use simple table/column names only.")