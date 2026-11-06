"""Thin ctypes wrappers around the Windows IP Helper API (iphlpapi.dll).

These calls work without administrator rights and without Npcap, so they are the
agent's dependable baseline on Windows. On other systems ``AVAILABLE`` is False and
callers fall back to other methods.
"""

from __future__ import annotations

import ctypes
import socket
import struct
import sys
import time
from dataclasses import dataclass

AVAILABLE = sys.platform == "win32"

if AVAILABLE:  # pragma: no cover - exercised on Windows only
    from ctypes import wintypes

    _iphlpapi = ctypes.WinDLL("iphlpapi.dll")

    class _MIB_IPFORWARDROW(ctypes.Structure):  # noqa: N801 - Windows struct name
        _fields_ = [
            (name, wintypes.DWORD)
            for name in (
                "dwForwardDest",
                "dwForwardMask",
                "dwForwardPolicy",
                "dwForwardNextHop",
                "dwForwardIfIndex",
                "dwForwardType",
                "dwForwardProto",
                "dwForwardAge",
                "dwForwardNextHopAS",
                "dwForwardMetric1",
                "dwForwardMetric2",
                "dwForwardMetric3",
                "dwForwardMetric4",
                "dwForwardMetric5",
            )
        ]

    _iphlpapi.GetBestRoute.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_MIB_IPFORWARDROW),
    ]
    _iphlpapi.GetBestRoute.restype = wintypes.DWORD
    _iphlpapi.SendARP.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.ULONG),
    ]
    _iphlpapi.SendARP.restype = wintypes.DWORD

    class _IP_OPTION_INFORMATION(ctypes.Structure):  # noqa: N801
        _fields_ = [
            ("Ttl", ctypes.c_ubyte),
            ("Tos", ctypes.c_ubyte),
            ("Flags", ctypes.c_ubyte),
            ("OptionsSize", ctypes.c_ubyte),
            ("OptionsData", ctypes.c_void_p),
        ]

    class _ICMP_ECHO_REPLY(ctypes.Structure):  # noqa: N801
        _fields_ = [
            ("Address", wintypes.ULONG),
            ("Status", wintypes.ULONG),
            ("RoundTripTime", wintypes.ULONG),
            ("DataSize", ctypes.c_ushort),
            ("Reserved", ctypes.c_ushort),
            ("Data", ctypes.c_void_p),
            ("Options", _IP_OPTION_INFORMATION),
        ]

    _iphlpapi.IcmpCreateFile.argtypes = []
    _iphlpapi.IcmpCreateFile.restype = wintypes.HANDLE
    _iphlpapi.IcmpCloseHandle.argtypes = [wintypes.HANDLE]
    _iphlpapi.IcmpCloseHandle.restype = wintypes.BOOL
    _iphlpapi.IcmpSendEcho.argtypes = [
        wintypes.HANDLE,
        wintypes.ULONG,
        ctypes.c_void_p,
        wintypes.WORD,
        ctypes.POINTER(_IP_OPTION_INFORMATION),
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    _iphlpapi.IcmpSendEcho.restype = wintypes.DWORD

# IP_STATUS codes returned by IcmpSendEcho (ipexport.h), the ones worth naming.
ICMP_STATUS = {
    0: "success",
    11002: "destination network unreachable",
    11003: "destination host unreachable",
    11010: "timed out",
    11013: "TTL expired in transit",
    11050: "general failure",
}


@dataclass(frozen=True)
class EchoReply:
    """The result of one ICMP echo request."""

    ok: bool
    rtt_ms: float | None  # None when there was no reply
    ttl: int | None = None
    status: str = "success"


def _to_dword(ip: str) -> int:
    """IPv4 dotted string -> DWORD in network byte order, as iphlpapi expects."""
    return struct.unpack("<I", socket.inet_aton(ip))[0]


def _from_dword(value: int) -> str:
    return socket.inet_ntoa(struct.pack("<I", value))


def best_route_next_hop(destination: str = "8.8.8.8") -> str | None:
    """The next hop Windows would use to reach ``destination`` (the default gateway).

    Returns None when there is no route or the next hop is on-link (0.0.0.0).
    """
    if not AVAILABLE:
        return None
    row = _MIB_IPFORWARDROW()
    if _iphlpapi.GetBestRoute(_to_dword(destination), 0, ctypes.byref(row)) != 0:
        return None
    hop = _from_dword(row.dwForwardNextHop)
    return None if hop == "0.0.0.0" else hop


def send_arp(ip: str) -> str | None:
    """Resolve ``ip`` to a MAC address with an ARP request sent by Windows.

    Blocks until the host answers or Windows gives up (about 1-3 seconds), so callers
    should run many in parallel. Returns ``aa:bb:cc:dd:ee:ff`` or None if no reply.
    """
    if not AVAILABLE:
        return None
    mac = (ctypes.c_ubyte * 8)()
    length = wintypes.ULONG(8)
    if _iphlpapi.SendARP(_to_dword(ip), 0, mac, ctypes.byref(length)) != 0:
        return None
    if length.value != 6:
        return None
    return ":".join(f"{b:02x}" for b in mac[:6])


_PAYLOAD = b"kinlan-echo-0123456789abcdefghij"  # 32 bytes, the same size Windows ping uses


def icmp_echo(ip: str, timeout_ms: int = 1000) -> EchoReply:
    """Send one ICMP echo request to ``ip`` through Windows and wait for the reply.

    Windows reports round-trip times in whole milliseconds; replies faster than 1 ms
    (common on a LAN) are timed with ``perf_counter`` instead, so they aren't shown as 0.
    """
    if not AVAILABLE:
        raise OSError("IcmpSendEcho is only available on Windows")
    handle = _iphlpapi.IcmpCreateFile()
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "IcmpCreateFile failed")
    reply_size = ctypes.sizeof(_ICMP_ECHO_REPLY) + len(_PAYLOAD) + 8
    buffer = ctypes.create_string_buffer(reply_size)
    try:
        started = time.perf_counter()
        count = _iphlpapi.IcmpSendEcho(
            handle, _to_dword(ip), _PAYLOAD, len(_PAYLOAD), None, buffer, reply_size, timeout_ms
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
    finally:
        _iphlpapi.IcmpCloseHandle(handle)
    reply = _ICMP_ECHO_REPLY.from_buffer(buffer)
    if count == 0:
        return EchoReply(ok=False, rtt_ms=None, status="timed out")
    if reply.Status != 0:
        status = ICMP_STATUS.get(reply.Status, f"IP status {reply.Status}")
        return EchoReply(ok=False, rtt_ms=None, status=status)
    rtt = float(reply.RoundTripTime) if reply.RoundTripTime >= 1 else round(elapsed_ms, 2)
    return EchoReply(ok=True, rtt_ms=rtt, ttl=reply.Options.Ttl)
