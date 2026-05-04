"""Usage statistics service backed by SQLite."""

import asyncio
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional


class StatsService:
    """Persist and summarize bot usage statistics."""

    WEEK_SECONDS = 7 * 24 * 60 * 60
    MONTH_SECONDS = 30 * 24 * 60 * 60

    def __init__(self, db_path: str = "./stats/bot_stats.sqlite3", cache_dir: str = "./cache"):
        self.db_path = Path(db_path)
        self.cache_dir = Path(cache_dir)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._schema_lock = asyncio.Lock()
        self._schema_ready = False

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema_sync(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS download_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    track_id TEXT NOT NULL,
                    files_count INTEGER NOT NULL,
                    bytes_sent INTEGER NOT NULL,
                    cache_hit INTEGER NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_download_events_created_at
                ON download_events(created_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_download_events_user_id
                ON download_events(user_id)
                """
            )

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        async with self._schema_lock:
            if self._schema_ready:
                return
            await asyncio.to_thread(self._ensure_schema_sync)
            self._schema_ready = True

    def _record_download_sync(
        self,
        user_id: int,
        track_id: str,
        files_count: int,
        bytes_sent: int,
        cache_hit: bool,
        created_at: float,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO download_events (
                    user_id,
                    track_id,
                    files_count,
                    bytes_sent,
                    cache_hit,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, track_id, files_count, bytes_sent, int(cache_hit), created_at),
            )

    async def record_download(
        self,
        user_id: int,
        track_id: str,
        files_count: int,
        bytes_sent: int,
        cache_hit: bool,
        created_at: Optional[float] = None,
    ) -> None:
        """Record one successful user request."""
        await self._ensure_schema()
        await asyncio.to_thread(
            self._record_download_sync,
            user_id,
            track_id,
            files_count,
            bytes_sent,
            cache_hit,
            time.time() if created_at is None else created_at,
        )

    def _count_unique_users(self, conn: sqlite3.Connection, since: Optional[float] = None) -> int:
        if since is None:
            row = conn.execute("SELECT COUNT(DISTINCT user_id) FROM download_events").fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(DISTINCT user_id) FROM download_events WHERE created_at >= ?",
                (since,),
            ).fetchone()
        return int(row[0] or 0)

    def _sum_metric(
        self,
        conn: sqlite3.Connection,
        expression: str,
        since: Optional[float] = None,
    ) -> int:
        if since is None:
            row = conn.execute(f"SELECT {expression} FROM download_events").fetchone()
        else:
            row = conn.execute(
                f"SELECT {expression} FROM download_events WHERE created_at >= ?",
                (since,),
            ).fetchone()
        return int(row[0] or 0)

    def _get_cache_summary_sync(self) -> dict[str, int]:
        if not self.cache_dir.exists():
            return {"files": 0, "bytes": 0}

        files_count = 0
        total_bytes = 0
        for path in self.cache_dir.glob("*.gpx"):
            if not path.is_file():
                continue
            files_count += 1
            total_bytes += path.stat().st_size

        return {"files": files_count, "bytes": total_bytes}

    def _get_summary_sync(self, now: float) -> dict[str, Any]:
        month_since = now - self.MONTH_SECONDS
        week_since = now - self.WEEK_SECONDS
        with self._connect() as conn:
            return {
                "users": {
                    "total": self._count_unique_users(conn),
                    "month": self._count_unique_users(conn, month_since),
                    "week": self._count_unique_users(conn, week_since),
                },
                "requests": {
                    "total": self._sum_metric(conn, "COUNT(*)"),
                    "month": self._sum_metric(conn, "COUNT(*)", month_since),
                    "week": self._sum_metric(conn, "COUNT(*)", week_since),
                },
                "files": {
                    "total": self._sum_metric(conn, "SUM(files_count)"),
                    "month": self._sum_metric(conn, "SUM(files_count)", month_since),
                    "week": self._sum_metric(conn, "SUM(files_count)", week_since),
                },
                "cache": self._get_cache_summary_sync(),
            }

    async def get_summary(self, now: Optional[float] = None) -> dict[str, Any]:
        """Return usage and cache summary."""
        await self._ensure_schema()
        return await asyncio.to_thread(self._get_summary_sync, time.time() if now is None else now)
