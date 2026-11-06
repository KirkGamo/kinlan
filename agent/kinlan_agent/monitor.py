"""Continuous latency sampling and outage detection.

Every tick (10 s by default) the agent sends one ICMP echo to the gateway and one to the
main internet target. If the internet target fails, a second internet target is asked
to confirm, so one unreliable server can't fake an outage.

Outage rules (docs/KinLAN_Technical_Plan.md, Section 3.4):

* **Down** after 3 ticks in a row where both internet targets fail. The cause is
  ``isp`` if the gateway still answered on the first failing tick, else ``lan``.
* **Up** after 2 ticks in a row where the internet answers again.

The outage's start time is the first failing tick and its end time the first good tick,
so durations are exact even though detection takes a few ticks.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from kinlan_agent.icmp import EchoReply, echo

# Candidates in order of preference. Some networks block some of these, sometimes only for
# a while (1.1.1.1 was unreachable for over an hour on the home test network on Nov 7).
DEFAULT_INTERNET_CANDIDATES = ("8.8.8.8", "9.9.9.9", "1.1.1.1", "208.67.222.222")
DOWN_AFTER_TICKS = 3
UP_AFTER_TICKS = 2
TARGET_RECHECK_S = 3600

Echo = Callable[[str, int], EchoReply]


def now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Sample:
    """One measurement, as stored in the outbox and sent in the ingest payload."""

    ts: datetime
    target: str  # "gateway" or "internet"
    ip: str
    rtt_ms: float | None
    ok: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "ts": self.ts.isoformat().replace("+00:00", "Z"),
            "target": self.target,
            "ip": self.ip,
            "rtt_ms": self.rtt_ms,
            "ok": self.ok,
        }


@dataclass
class Outage:
    """An internet outage seen by the agent. ``ended_at`` is None while it's ongoing."""

    started_at: datetime
    cause: str  # "isp" or "lan"
    ended_at: datetime | None = None

    @property
    def duration_s(self) -> float | None:
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, object]:
        def iso(value: datetime | None) -> str | None:
            return value.isoformat().replace("+00:00", "Z") if value else None

        return {"started_at": iso(self.started_at), "ended_at": iso(self.ended_at),
                "cause": self.cause}


@dataclass(frozen=True)
class Tick:
    """What one monitoring tick observed."""

    ts: datetime
    gateway_ok: bool | None  # None when there is no gateway to ping
    internet_ok: bool  # True if the main or the confirming target answered
    samples: list[Sample] = field(default_factory=list)


@dataclass(frozen=True)
class OutageEvent:
    kind: str  # "started" or "ended"
    outage: Outage


def choose_internet_targets(
    candidates: Sequence[str] = DEFAULT_INTERNET_CANDIDATES,
    send: Echo = echo,
    attempts: int = 2,
    timeout_ms: int = 1000,
    need: int = 2,
) -> list[str]:
    """Pick ``need`` internet targets that answer ping right now.

    Candidates are tried in order; one counts as working if any of ``attempts`` echoes
    gets a reply. If fewer than ``need`` work (for example, the internet is down at
    startup), the list is filled with the remaining candidates in order, so the monitor
    always has targets and an outage is detected rather than hidden.
    """
    working = [
        ip
        for ip in candidates
        if any(send(ip, timeout_ms).ok for _ in range(attempts))
    ][:need]
    for ip in candidates:
        if len(working) >= need:
            break
        if ip not in working:
            working.append(ip)
    return working


class OutageDetector:
    """A small state machine fed one :class:`Tick` at a time."""

    def __init__(self, down_after: int = DOWN_AFTER_TICKS, up_after: int = UP_AFTER_TICKS):
        self.down_after = down_after
        self.up_after = up_after
        self.current: Outage | None = None
        self._failing: list[Tick] = []
        self._recovering: list[Tick] = []

    def update(self, tick: Tick) -> OutageEvent | None:
        """Process one tick; return an event when an outage starts or ends."""
        if self.current is None:
            if tick.internet_ok:
                self._failing.clear()
                return None
            self._failing.append(tick)
            if len(self._failing) < self.down_after:
                return None
            first = self._failing[0]
            cause = "isp" if first.gateway_ok else "lan"
            self.current = Outage(started_at=first.ts, cause=cause)
            self._failing.clear()
            return OutageEvent("started", self.current)

        if not tick.internet_ok:
            self._recovering.clear()
            return None
        self._recovering.append(tick)
        if len(self._recovering) < self.up_after:
            return None
        self.current.ended_at = self._recovering[0].ts
        ended, self.current = self.current, None
        self._recovering.clear()
        return OutageEvent("ended", ended)


class Monitor:
    """Takes one sample per tick and tracks outages.

    The scheduling loop (every ``monitor_interval_s``) lives in the runner; this class
    only does one tick at a time, which keeps it easy to test.
    """

    def __init__(
        self,
        gateway: str | None,
        internet_targets: Sequence[str],
        send: Echo = echo,
        clock: Callable[[], datetime] = now_utc,
        timeout_ms: int = 1000,
    ):
        if len(internet_targets) < 2:
            raise ValueError("need a main and a confirming internet target")
        self.gateway = gateway
        self.primary, self.confirm = internet_targets[0], internet_targets[1]
        self.send = send
        self.clock = clock
        self.timeout_ms = timeout_ms
        self.detector = OutageDetector()

    def tick(self) -> tuple[Tick, OutageEvent | None]:
        """Ping the gateway and the internet once; return the tick and any outage event."""
        ts = self.clock()
        samples: list[Sample] = []
        gateway_ok: bool | None = None
        if self.gateway:
            reply = self.send(self.gateway, self.timeout_ms)
            gateway_ok = reply.ok
            samples.append(Sample(ts, "gateway", self.gateway, reply.rtt_ms, reply.ok))

        reply = self.send(self.primary, self.timeout_ms)
        samples.append(Sample(ts, "internet", self.primary, reply.rtt_ms, reply.ok))
        internet_ok = reply.ok
        if not internet_ok:
            confirm = self.send(self.confirm, self.timeout_ms)
            samples.append(Sample(ts, "internet", self.confirm, confirm.rtt_ms, confirm.ok))
            internet_ok = confirm.ok

        tick = Tick(ts=ts, gateway_ok=gateway_ok, internet_ok=internet_ok, samples=samples)
        return tick, self.detector.update(tick)
