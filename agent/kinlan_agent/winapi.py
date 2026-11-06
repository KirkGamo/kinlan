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
