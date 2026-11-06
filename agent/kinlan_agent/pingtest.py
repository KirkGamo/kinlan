"""Ping a device several times and summarize the results (required Feature 2: Connectivity Testing).

The statistics match what Windows ``ping`` reports (sent, received, loss, min/avg/max)
plus jitter, the average change in round-trip time between consecutive replies.
See docs/KinLAN_Technical_Plan.md, Section 3.2 (``pingtest.py``) and the command
contract for ``ping_test`` in Section 4.3.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import pairwise

from kinlan_agent.icmp import EchoReply, echo

DEFAULT_COUNT = 10
DEFAULT_INTERVAL_S = 0.5
DEFAULT_TIMEOUT_MS = 1000


@dataclass(frozen=True)
class PingStats:
    """Summary of a ping test against one target."""

    target: str
    sent: int
    received: int
    loss_pct: float
    min_ms: float | None
    avg_ms: float | None
    max_ms: float | None
    jitter_ms: float | None
    rtts_ms: tuple[float | None, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """JSON-friendly form, matching the ``ping_test`` command result."""
        return {
            "target": self.target,
            "sent": self.sent,
            "received": self.received,
            "loss_pct": self.loss_pct,
            "min_ms": self.min_ms,
            "avg_ms": self.avg_ms,
            "max_ms": self.max_ms,
            "jitter_ms": self.jitter_ms,
        }


def summarize(target: str, replies: Sequence[EchoReply]) -> PingStats:
    """Turn a sequence of echo replies into :class:`PingStats` (pure; easy to test)."""
    rtts = [r.rtt_ms for r in replies if r.ok and r.rtt_ms is not None]
    sent = len(replies)
    received = len(rtts)
    loss = round(100 * (sent - received) / sent, 1) if sent else 0.0
    jitter = None
    if len(rtts) >= 2:
        jitter = round(sum(abs(b - a) for a, b in pairwise(rtts)) / (len(rtts) - 1), 2)
    return PingStats(
        target=target,
        sent=sent,
        received=received,
        loss_pct=loss,
        min_ms=min(rtts) if rtts else None,
        avg_ms=round(sum(rtts) / received, 2) if rtts else None,
        max_ms=max(rtts) if rtts else None,
        jitter_ms=jitter,
        rtts_ms=tuple(r.rtt_ms if r.ok else None for r in replies),
    )


def ping_test(
    target: str,
    count: int = DEFAULT_COUNT,
    interval_s: float = DEFAULT_INTERVAL_S,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    send: Callable[[str, int], EchoReply] = echo,
    sleep: Callable[[float], None] = time.sleep,
) -> PingStats:
    """Send ``count`` echo requests to ``target``, ``interval_s`` apart, and summarize them."""
    if count < 1:
        raise ValueError("count must be at least 1")
    replies: list[EchoReply] = []
    for i in range(count):
        if i:
            sleep(interval_s)
        replies.append(send(target, timeout_ms))
    return summarize(target, replies)
