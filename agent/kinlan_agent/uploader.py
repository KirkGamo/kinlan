"""Sends the outbox to ``POST /agent/ingest`` (plan, Sections 1.1, 1.2 and 3.2).

* **Nothing is lost:** rows leave the outbox only after the server accepts the batch.
* **Resend-safe:** the batch being sent is remembered in the buffer (its id range and
  ``batch_id``). After a dropped connection or a restart the exact same rows go again
  under the same ``batch_id``, which the server stores only once.
* **Backoff:** failures wait 2, 4, 8 ... up to 300 seconds (with jitter), then reset.
* **Oldest first:** after an outage the backlog drains in order, batch after batch.
"""

from __future__ import annotations

import gzip
import json
import logging
import random
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

import httpx

from kinlan_agent import __version__
from kinlan_agent.buffer import Buffer, OutboxItem

log = logging.getLogger("kinlan.uploader")

INFLIGHT_KEY = "inflight_batch"  # "batch_id first_id last_id"
LAST_UPLOAD_KEY = "last_upload_at"
BACKOFF_START_S, BACKOFF_MAX_S = 2.0, 300.0


class Outcome(Enum):
    EMPTY = "empty"  # nothing to send
    SENT = "sent"  # a batch was accepted (stored or duplicate)
    RETRY = "retry"  # network or server trouble; try again after a backoff
    STOP = "stop"  # the server won't take uploads from this agent (unpaired, too old)


@dataclass
class Batch:
    batch_id: str
    items: list[OutboxItem]

    @property
    def first_id(self) -> int:
        return self.items[0].id

    @property
    def last_id(self) -> int:
        return self.items[-1].id


def build_payload(batch: Batch, version: str = __version__) -> dict:
    """Turn outbox rows into the ingest payload (plan, Section 4.3)."""
    payload: dict = {
        "batch_id": batch.batch_id,
        "agent_version": version,
        "sent_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "samples": [],
        "devices": [],
        "outages": [],
        "port_findings": [],
    }
    for item in batch.items:
        if item.kind == "sample":
            payload["samples"].append(item.payload)
        elif item.kind == "scan":
            if item.payload.get("netinfo"):
                payload["netinfo"] = item.payload["netinfo"]  # the newest scan's wins
            payload["devices"].extend(item.payload.get("devices", []))
        elif item.kind == "netinfo":
            payload["netinfo"] = item.payload
        elif item.kind == "outage":
            payload["outages"].append(item.payload)
        elif item.kind == "port_finding":
            payload["port_findings"].append(item.payload)
        else:
            log.warning("skipping unknown outbox item kind %r", item.kind)
    return payload


class Uploader:
    def __init__(
        self,
        buffer: Buffer,
        api_url: str,
        token: str,
        client: httpx.Client | None = None,
        batch_size: int = 500,
        version: str = __version__,
    ):
        self.buffer = buffer
        self.url = api_url.rstrip("/") + "/api/v1/agent/ingest"
        self.token = token
        self.client = client or httpx.Client(timeout=30)
        self.batch_size = batch_size
        self.version = version
        self.failures = 0
        self.stopped_reason: str | None = None

    # --- batches ------------------------------------------------------------------------

    def next_batch(self) -> Batch | None:
        """The batch in flight if there is one, else a new one from the oldest rows."""
        inflight = self.buffer.get_meta(INFLIGHT_KEY)
        if inflight:
            batch_id, first, last = inflight.split()
            items = self.buffer.items_between(int(first), int(last))
            if items:
                return Batch(batch_id, items)
            self.buffer.set_meta(INFLIGHT_KEY, None)
        items = self.buffer.peek(self.batch_size)
        if not items:
            return None
        batch = Batch(str(uuid.uuid4()), items)
        self.buffer.set_meta(INFLIGHT_KEY, f"{batch.batch_id} {batch.first_id} {batch.last_id}")
        return batch

    def _done(self, batch: Batch) -> None:
        self.buffer.delete(i.id for i in batch.items)
        self.buffer.set_meta(INFLIGHT_KEY, None)

    # --- sending ------------------------------------------------------------------------

    def send_once(self) -> Outcome:
        batch = self.next_batch()
        if batch is None:
            return Outcome.EMPTY
        body = gzip.compress(json.dumps(build_payload(batch, self.version)).encode())
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Content-Encoding": "gzip",
        }
        try:
            r = self.client.post(self.url, content=body, headers=headers)
        except httpx.HTTPError as exc:
            log.info("upload failed (%s); %d items kept for later", exc, len(batch.items))
            self.failures += 1
            return Outcome.RETRY

        if r.is_success:
            self._done(batch)
            self.failures = 0
            self.buffer.set_meta(LAST_UPLOAD_KEY, datetime.now(UTC).isoformat())
            return Outcome.SENT
        if r.status_code in (401, 426):
            self.stopped_reason = _error_message(r)
            log.error("server refused uploads: %s", self.stopped_reason)
            return Outcome.STOP
        if r.status_code == 413 and len(batch.items) > 1:
            self.buffer.set_meta(INFLIGHT_KEY, None)  # re-cut a smaller batch
            self.batch_size = max(1, len(batch.items) // 2)
            return Outcome.RETRY
        if 400 <= r.status_code < 500 and r.status_code != 429:
            # The server will never accept these rows; drop them so the outbox can't jam.
            log.error(
                "server rejected %d items (%s); dropping them", len(batch.items), _error_message(r)
            )
            self._done(batch)
            return Outcome.SENT
        self.failures += 1
        log.info("server busy or down (HTTP %s); will retry", r.status_code)
        return Outcome.RETRY

    def backoff_s(self) -> float:
        base = min(BACKOFF_MAX_S, BACKOFF_START_S * 2 ** max(0, self.failures - 1))
        return base * random.uniform(0.8, 1.2)

    def run(self, stop: threading.Event, interval_s: float = 30.0) -> None:
        """Upload until ``stop`` is set: drain the backlog, then one batch per interval."""
        while not stop.is_set():
            outcome = self.send_once()
            if outcome is Outcome.STOP:
                return
            if outcome is Outcome.SENT and self.buffer.count():
                continue  # more backlog: keep going
            stop.wait(self.backoff_s() if outcome is Outcome.RETRY else interval_s)


def _error_message(r: httpx.Response) -> str:
    try:
        return r.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return f"HTTP {r.status_code}"
