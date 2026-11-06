"""Facts about the network this PC is on: local IP, subnet, gateway, DNS servers and interface.

Everything here is read from the operating system; nothing sends traffic except
``outbound_ip``, which opens a UDP socket without sending a packet.
See docs/KinLAN_Technical_Plan.md, Section 3.2 (``netinfo.py``).
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field

import psutil

from kinlan_agent import winapi

# Any routable address works for the UDP trick; no packet is sent to it.
_ROUTE_PROBE = ("8.8.8.8", 80)
# Networks wider than this are scanned only around the host (see scan_network()).
DEFAULT_MAX_SCAN_PREFIX = 22


@dataclass(frozen=True)
class NetInfo:
    """A snapshot of the local network configuration."""

    local_ip: str
    netmask: str
    network: ipaddress.IPv4Network
    gateway: str | None
    interface_name: str
    interface_mac: str | None
    dns_servers: list[str] = field(default_factory=list)
    pcap_iface: str | None = None  # Npcap device name used for ARP scans, if known

    @property
    def is_apipa(self) -> bool:
        """True when Windows self-assigned a 169.254.x.x address because DHCP failed."""
        return is_apipa(self.local_ip)

    def to_dict(self) -> dict[str, object]:
        """JSON-friendly form, used in the ingest payload (``netinfo``)."""
        return {
            "local_ip": self.local_ip,
            "cidr": str(self.network),
            "gateway": self.gateway,
            "interface": self.interface_name,
            "dns_servers": list(self.dns_servers),
        }


def outbound_ip(probe: tuple[str, int] = _ROUTE_PROBE) -> str:
    """Return the IPv4 address the OS would use to reach the internet.

    Connecting a UDP socket only asks the routing table which source address to use;
    UDP is connectionless, so no packet leaves the machine.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect(probe)
        return sock.getsockname()[0]


def is_apipa(ip: str) -> bool:
    """True for link-local 169.254.0.0/16 addresses (no DHCP lease)."""
    return ipaddress.ip_address(ip) in ipaddress.ip_network("169.254.0.0/16")


def find_interface(
    ip: str, addrs: dict[str, list] | None = None
) -> tuple[str, str, str | None]:
    """Find the adapter that owns ``ip``. Returns ``(name, netmask, mac)``.

    ``addrs`` defaults to ``psutil.net_if_addrs()``; tests pass a fake mapping.
    Raises LookupError if no adapter has that address.
    """
    addrs = psutil.net_if_addrs() if addrs is None else addrs
    for name, entries in addrs.items():
        ipv4 = [e for e in entries if e.family == socket.AF_INET and e.address == ip]
        if not ipv4:
            continue
        mac = next((e.address for e in entries if e.family == psutil.AF_LINK), None)
        return name, ipv4[0].netmask, normalize_mac(mac) if mac else None
    raise LookupError(f"no network adapter has the address {ip}")


def scan_network(
    ip: str, netmask: str, max_prefix: int = DEFAULT_MAX_SCAN_PREFIX
) -> ipaddress.IPv4Network:
    """The range to scan: the adapter's subnet, or the host's /24 if the subnet is wider
    than ``/max_prefix`` (a /16 would be 65,534 addresses)."""
    network = ipaddress.ip_interface(f"{ip}/{netmask}").network
    if network.prefixlen < max_prefix:
        return ipaddress.ip_network(f"{ip}/24", strict=False)
    return network


def default_gateway() -> str | None:
    """The default gateway's IPv4 address, or None if there is no default route.

    Asks Windows directly (GetBestRoute), which needs neither admin rights nor Npcap,
    and falls back to Scapy's route table on other systems.
    """
    gateway = winapi.best_route_next_hop(_ROUTE_PROBE[0])
    if gateway:
        return gateway
    _iface, scapy_gateway = _scapy_route()
    return scapy_gateway


def pcap_interface() -> str | None:
    """The Npcap device name for the default route, used by Scapy ARP scans.

    None when Scapy or Npcap is unavailable; discovery then uses Windows SendARP.
    """
    iface, _gateway = _scapy_route()
    return iface


def _scapy_route() -> tuple[str | None, str | None]:
    """Return ``(iface, gateway)`` for the default route from Scapy, or ``(None, None)``."""
    try:
        import scapy.route  # noqa: F401 - importing it fills conf.route; Scapy loads slowly
        from scapy.config import conf

        iface, _src, gateway = conf.route.route("0.0.0.0")
    except Exception:  # noqa: BLE001 - any Scapy/Npcap failure means "unknown"
        return None, None
    gateway = None if not gateway or gateway == "0.0.0.0" else gateway
    return (str(iface) if iface else None), gateway


def dns_servers() -> list[str]:
    """IPv4 DNS servers configured on this PC (read from the system by dnspython)."""
    try:
        import dns.resolver

        servers = dns.resolver.Resolver(configure=True).nameservers
    except Exception:  # noqa: BLE001 - no usable resolver configuration
        return []
    return [s for s in map(str, servers) if ipaddress.ip_address(s).version == 4]


def normalize_mac(mac: str) -> str:
    """Return a MAC address as lower-case, colon-separated hex (``aa:bb:cc:dd:ee:ff``)."""
    digits = "".join(ch for ch in mac if ch.isalnum()).lower()
    if len(digits) != 12 or any(ch not in "0123456789abcdef" for ch in digits):
        raise ValueError(f"not a MAC address: {mac!r}")
    return ":".join(digits[i : i + 2] for i in range(0, 12, 2))


def get_netinfo(max_prefix: int = DEFAULT_MAX_SCAN_PREFIX) -> NetInfo:
    """Collect a full :class:`NetInfo` snapshot for the adapter that reaches the internet."""
    ip = outbound_ip()
    name, netmask, mac = find_interface(ip)
    return NetInfo(
        local_ip=ip,
        netmask=netmask,
        network=scan_network(ip, netmask, max_prefix),
        gateway=default_gateway(),
        interface_name=name,
        interface_mac=mac,
        dns_servers=dns_servers(),
        pcap_iface=pcap_interface(),
    )
