"""Local SQLite store that keeps measurements while the internet is down.

Everything the agent wants to upload goes into the **outbox** first; the uploader sends
it oldest-first and deletes rows only after the server accepts them, so nothing is lost
if the connection drops or the PC restarts. The **outages** table remembers an outage
that is still open, so a restart in the middle of an outage keeps its true start time.

Limits: rows older than 7 days are dropped, and the oldest rows go first if the data
grows past 50 MB. See docs/KinLAN_Technical_Plan.md, Section 3.2 (``buffer.py``).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

MAX_AGE = timedelta(days=7)
MAX_BYTES = 50 * 1024 * 1024
DEFAULT_PATH = Path(os.environ.get("PROGRAMDATA", Path.home())) / "KinLAN" / "buffer.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT    NOT NULL,          -- sample, device, outage, port_finding, ...
    payload     TEXT    NOT NULL,          -- JSON
    created_at  TEXT    NOT NULL           -- ISO 8601 UTC
);
CREATE INDEX IF NOT EXISTS outbox_created ON outbox (created_at);
CREATE TABLE IF NOT EXISTS outages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT    NOT NULL,
    ended_at    TEXT,
    cause       TEXT    NOT NULL
);
"""


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class OutboxItem:
    id: int
    kind: str
    payload: dict
    created_at: datetime


@dataclass(frozen=True)
class OpenOutage:
    id: int
    started_at: datetime
    cause: str


class Buffer:
    """Thread-safe wrapper around the agent's SQLite file."""

    def __init__(self, path: Path | str = DEFAULT_PATH):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")  # safe against crashes mid-write
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> Buffer:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- outbox ---------------------------------------------------------------------

    def add(self, kind: str, payload: dict, now: datetime | None = None) -> int:
        """Queue one item for upload; returns its row id."""
        return self.add_many(kind, [payload], now)[0]

    def add_many(
        self, kind: str, payloads: Iterable[dict], now: datetime | None = None
    ) -> list[int]:
        """Queue several items of the same kind in one transaction."""
        created = _iso(now or datetime.now(UTC))
        ids = []
        with self._lock:
            self._db.execute("BEGIN")
            try:
                for payload in payloads:
                    cur = self._db.execute(
                        "INSERT INTO outbox (kind, payload, created_at) VALUES (?, ?, ?)",
                        (kind, json.dumps(payload, separators=(",", ":")), created),
                    )
                    ids.append(cur.lastrowid)
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
        return ids

    def peek(self, limit: int = 500) -> list[OutboxItem]:
        """The oldest ``limit`` items, without removing them."""
        with self._lock:
            rows = self._db.execute(
                "SELECT id, kind, payload, created_at FROM outbox ORDER BY id LIMIT ?", (limit,)
            ).fetchall()
        return [OutboxItem(r[0], r[1], json.loads(r[2]), _parse(r[3])) for r in rows]

    def delete(self, ids: Iterable[int]) -> int:
        """Remove items the server has accepted. Returns how many were deleted."""
        ids = list(ids)
        if not ids:
            return 0
        with self._lock:
            cur = self._db.executemany("DELETE FROM outbox WHERE id = ?", [(i,) for i in ids])
        return cur.rowcount

    def count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]

    def data_bytes(self) -> int:
        """Bytes in use (excluding free pages left behind by deletes)."""
        with self._lock:
            page_size = self._db.execute("PRAGMA page_size").fetchone()[0]
            pages = self._db.execute("PRAGMA page_count").fetchone()[0]
            free = self._db.execute("PRAGMA freelist_count").fetchone()[0]
        return (pages - free) * page_size

    def prune(
        self,
        now: datetime | None = None,
        max_age: timedelta = MAX_AGE,
        max_bytes: int = MAX_BYTES,
        batch: int = 1000,
    ) -> int:
        """Drop items older than ``max_age``, then the oldest items while over ``max_bytes``.

        Returns how many items were removed. Runs hourly from the runner.
        """
        cutoff = _iso((now or datetime.now(UTC)) - max_age)
        with self._lock:
            removed = self._db.execute(
                "DELETE FROM outbox WHERE created_at < ?", (cutoff,)
            ).rowcount
        while self.data_bytes() > max_bytes:
            with self._lock:
                cur = self._db.execute(
                    "DELETE FROM outbox WHERE id IN (SELECT id FROM outbox ORDER BY id LIMIT ?)",
                    (batch,),
                )
            if cur.rowcount == 0:
                break
            removed += cur.rowcount
        return removed

    # --- outages --------------------------------------------------------------------

    def open_outage(self, started_at: datetime, cause: str) -> int:
        """Remember an outage that has just started."""
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO outages (started_at, cause) VALUES (?, ?)", (_iso(started_at), cause)
            )
        return cur.lastrowid

    def current_outage(self) -> OpenOutage | None:
        """The outage that is still open, if any (used to resume after a restart)."""
        with self._lock:
            row = self._db.execute(
                "SELECT id, started_at, cause FROM outages WHERE ended_at IS NULL "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return OpenOutage(row[0], _parse(row[1]), row[2]) if row else None

    def close_outage(self, outage_id: int, ended_at: datetime) -> dict:
        """Mark an outage as over and queue it for upload. Returns the uploaded payload."""
        with self._lock:
            row = self._db.execute(
                "SELECT started_at, cause FROM outages WHERE id = ?", (outage_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"no outage with id {outage_id}")
            self._db.execute(
                "UPDATE outages SET ended_at = ? WHERE id = ?", (_iso(ended_at), outage_id)
            )
        payload = {"started_at": row[0], "ended_at": _iso(ended_at), "cause": row[1]}
        self.add("outage", payload, now=ended_at)
        return payload
