"""Risky-port check (plan, Sections 3.2 and 3.5; course Feature 5).

Tries a TCP connection to a few well-known ports on each device: FTP (21) and Telnet (23) send
passwords unencrypted, SMB file sharing (445), Remote Desktop (3389) and VNC screen sharing (5900)
let someone in, and 80/8080 are web admin pages (reported as information). A port "answers" when
the connection opens within half a second; nothing is sent over it, and it is closed at once.

Up to 100 connections run at a time, so a home network of 30 devices takes about a second. The
agent's own PC is skipped: checked from itself, Windows always answers on 445, which says nothing
about what other devices on the network can reach.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

PORTS: Mapping[int, str] = {
    21: "ftp",
    23: "telnet",
    80: "http",
    445: "smb",
    3389: "rdp",
    5900: "vnc",
    8080: "http",
}
TIMEOUT_S = 0.5
CONCURRENCY = 100

Opener = Callable[[str, int, float], Awaitable[bool]]


@dataclass(frozen=True)
class Target:
    mac: str
    ip: str


@dataclass
class PortCheck:
    ports: list[int]
    macs: list[str]  # every device that was tried
    open: list[dict] = field(default_factory=list)  # {"mac", "port", "service"}
    duration_ms: int = 0
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        """The command result and the ingest `port_checks` item (server PortCheckIn)."""
        return {
            "checked_at": self.checked_at.isoformat().replace("+00:00", "Z"),
            "ports": self.ports,
            "macs": self.macs,
            "open": self.open,
            "duration_ms": self.duration_ms,
        }


async def tcp_open(ip: str, port: int, timeout: float) -> bool:
    """True if a TCP connection to ip:port opens within `timeout` seconds."""
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout)
    except (OSError, TimeoutError):
        return False
    writer.close()
    with contextlib.suppress(OSError):  # the other side may reset it first; it answered anyway
        await writer.wait_closed()
    return True


async def _check(
    targets: list[Target], ports: Mapping[int, str], timeout: float, limit: int, opener: Opener
) -> list[dict]:
    gate = asyncio.Semaphore(limit)

    async def one(t: Target, port: int) -> dict | None:
        async with gate:
            if await opener(t.ip, port, timeout):
                return {"mac": t.mac, "port": port, "service": ports[port]}
            return None

    found = await asyncio.gather(*(one(t, p) for t in targets for p in ports))
    return [f for f in found if f is not None]


def check(
    targets: Iterable[Target],
    skip_ip: str | None = None,
    ports: Mapping[int, str] = PORTS,
    timeout: float = TIMEOUT_S,
    concurrency: int = CONCURRENCY,
    opener: Opener = tcp_open,
) -> PortCheck:
    """Check every target's ports (except the agent's own address, `skip_ip`)."""
    tried = [t for t in targets if t.ip and t.ip != skip_ip]
    started = time.monotonic()
    found = asyncio.run(_check(tried, ports, timeout, concurrency, opener)) if tried else []
    found.sort(key=lambda f: (f["mac"], f["port"]))
    return PortCheck(
        ports=sorted(ports),
        macs=[t.mac for t in tried],
        open=found,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
