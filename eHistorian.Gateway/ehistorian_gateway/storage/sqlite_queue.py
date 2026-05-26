from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path

import aiosqlite

from ehistorian_gateway.models.event import PersistedBatch


class SQLiteQueue:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._logger = logging.getLogger("ehistorian_gateway.sqlite_queue")
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS outbound_batches (
                    batch_id TEXT PRIMARY KEY,
                    gateway_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS ix_outbound_batches_status_available ON outbound_batches(status, available_at)"
            )
            await db.execute("UPDATE outbound_batches SET status = 'pending' WHERE status = 'sending'")
            await db.commit()

    async def enqueue_batch(self, batch: PersistedBatch) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO outbound_batches (
                    batch_id, gateway_id, payload, attempts, status, available_at, last_error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'pending', ?, NULL, ?, ?)
                """,
                (batch.batch_id, batch.gateway_id, batch.payload_json(), batch.attempts, now, now, now),
            )
            await db.commit()

    async def lease_next_batch(self) -> PersistedBatch | None:
        async with self._lock:
            async with aiosqlite.connect(self._path) as db:
                db.row_factory = aiosqlite.Row
                now = datetime.now(timezone.utc).isoformat()
                await db.execute("BEGIN IMMEDIATE")
                row = await (
                    await db.execute(
                        """
                        SELECT batch_id, gateway_id, payload, attempts
                        FROM outbound_batches
                        WHERE status = 'pending' AND available_at <= ?
                        ORDER BY created_at ASC
                        LIMIT 1
                        """,
                        (now,),
                    )
                ).fetchone()

                if row is None:
                    await db.commit()
                    return None

                await db.execute(
                    "UPDATE outbound_batches SET status = 'sending', updated_at = ? WHERE batch_id = ?",
                    (now, row["batch_id"]),
                )
                await db.commit()
                return PersistedBatch.from_payload(row["batch_id"], row["gateway_id"], row["payload"], row["attempts"])

    async def mark_sent(self, batch_id: str) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute("DELETE FROM outbound_batches WHERE batch_id = ?", (batch_id,))
            await db.commit()

    async def mark_retry(self, batch_id: str, error: str, delay_seconds: float) -> None:
        next_attempt_at = (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                UPDATE outbound_batches
                SET status = 'pending',
                    attempts = attempts + 1,
                    available_at = ?,
                    last_error = ?,
                    updated_at = ?
                WHERE batch_id = ?
                """,
                (next_attempt_at, error[:2000], now, batch_id),
            )
            await db.commit()

    async def pending_count(self) -> int:
        async with aiosqlite.connect(self._path) as db:
            row = await (await db.execute("SELECT COUNT(*) FROM outbound_batches")).fetchone()
            return int(row[0]) if row else 0