"""One ICMP echo, on any platform.

On Windows this uses IcmpSendEcho (no admin rights needed). Elsewhere it uses icmplib
in unprivileged mode, which works on Linux and macOS without root.
"""

from __future__ import annotations

from kinlan_agent import winapi
from kinlan_agent.winapi import EchoReply

__all__ = ["EchoReply", "echo"]


def echo(ip: str, timeout_ms: int = 1000) -> EchoReply:
    """Send one echo request to ``ip``; never raises for an unreachable host."""
    if winapi.AVAILABLE:
        try:
            return winapi.icmp_echo(ip, timeout_ms)
        except OSError as exc:
            return EchoReply(ok=False, rtt_ms=None, status=f"error: {exc}")
    return _icmplib_echo(ip, timeout_ms)


def _icmplib_echo(ip: str, timeout_ms: int) -> EchoReply:  # pragma: no cover - non-Windows
    import icmplib

    try:
        host = icmplib.ping(ip, count=1, timeout=timeout_ms / 1000, privileged=False)
    except icmplib.ICMPLibError as exc:
        return EchoReply(ok=False, rtt_ms=None, status=f"error: {exc}")
    if not host.is_alive:
        return EchoReply(ok=False, rtt_ms=None, status="timed out")
    return EchoReply(ok=True, rtt_ms=round(host.avg_rtt, 2))
