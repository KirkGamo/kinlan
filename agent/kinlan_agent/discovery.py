"""Find the active devices on the local network (required Feature 1: Network Discovery).

Devices are found with ARP, which works at layer 2: every device on the subnet must
answer an ARP request to receive traffic, even if its firewall ignores ping. Two ways
of sending ARP are supported:

* **Scapy + Npcap** sends one broadcast ARP request per address and collects every
  reply at once, resending twice to addresses that stay silent (phones in power-saving
  mode often miss the first request). About 7-8 s for a /24.
* **Windows SendARP** asks Windows to resolve each address. Needs no Npcap and no
  admin rights; addresses are resolved in parallel threads (about 5-15 s for a /24).

See docs/KinLAN_Technical_Plan.md, Section 3.2 (``discovery.py``).
"""

from __future__ import annotations

import ipaddress
import socket
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field

from kinlan_agent import vendors, winapi
from kinlan_agent.netinfo import NetInfo, normalize_mac

ARP_TIMEOUT_S = 2.0
ARP_RETRIES = 2  # resends to non-responders; one pass missed sleeping phones in testing
WINDOWS_ARP_WORKERS = 64
HOSTNAME_TIMEOUT_S = 1.5
HOSTNAME_WORKERS = 32


@dataclass(frozen=True)
class Device:
    """One device found on the network."""

    ip: str
    mac: str
    vendor: str | None = None
    hostname: str | None = None
    is_gateway: bool = False
    is_self: bool = False

    def to_dict(self) -> dict[str, object]:
        """JSON-friendly form, used in the ingest payload (``devices``)."""
        return {
            "ip": self.ip,
            "mac": self.mac,
            "vendor": self.vendor,
            "hostname": self.hostname,
            "is_gateway": self.is_gateway,
            "is_self": self.is_self,
        }


@dataclass(frozen=True)
class ScanResult:
    """The outcome of one discovery scan."""

    devices: list[Device]
    method: str  # "scapy" or "windows"
    network: str
    duration_ms: int
    errors: list[str] = field(default_factory=list)


def arp_targets(network: ipaddress.IPv4Network) -> list[str]:
    """Host addresses to ask: the network and broadcast addresses can never answer.

    A Wireshark capture of an early version showed .0 and .255 being asked three times
    each per /24 scan; this keeps every request useful.
    """
    return [str(ip) for ip in network.hosts()]


def arp_scan_scapy(
    network: ipaddress.IPv4Network,
    iface: str | None,
    timeout: float = ARP_TIMEOUT_S,
    retries: int = ARP_RETRIES,
) -> dict[str, str]:
    """Broadcast an ARP request to every address in ``network`` with Scapy/Npcap.

    Returns ``{ip: mac}`` for every reply. Raises if Scapy or Npcap is unusable.
    """
    from scapy.layers.l2 import ARP, Ether  # imported lazily: Scapy loads slowly
    from scapy.sendrecv import srp

    answered, _unanswered = srp(
        Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=arp_targets(network)),
        iface=iface,
        timeout=timeout,
        retry=retries,
        verbose=False,
    )
    return {reply.psrc: normalize_mac(reply.hwsrc) for _request, reply in answered}


def arp_scan_windows(
    network: ipaddress.IPv4Network,
    workers: int = WINDOWS_ARP_WORKERS,
    send_arp: Callable[[str], str | None] = winapi.send_arp,
) -> dict[str, str]:
    """Resolve every host address in ``network`` with Windows SendARP, in parallel.

    ``send_arp`` is injectable for tests. Returns ``{ip: mac}`` for hosts that answered.
    """
    hosts = arp_targets(network)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        macs = list(pool.map(send_arp, hosts))
    return {ip: normalize_mac(mac) for ip, mac in zip(hosts, macs, strict=True) if mac}


LOCAL_SUFFIXES = (".local", ".lan", ".home", ".home.arpa", ".localdomain", ".internal")


def ptr_lookup_via(server: str, timeout: float = HOSTNAME_TIMEOUT_S) -> Callable[[str], str]:
    """Return a resolver that asks ``server`` (usually the router) for an IP's PTR name.

    Home routers answer with the names devices gave over DHCP, which is far more
    accurate than an ISP's DNS server.
    """

    def lookup(ip: str) -> str:
        import dns.resolver
        import dns.reversename

        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = [server]
        resolver.lifetime = timeout
        answer = resolver.resolve(dns.reversename.from_address(ip), "PTR")
        return str(answer[0])

    return lookup


def system_ptr_lookup(ip: str) -> str:
    """Reverse lookup through the system's resolver (any configured DNS server)."""
    return socket.gethostbyaddr(ip)[0]


def resolve_hostnames(
    ips: Iterable[str],
    timeout: float = HOSTNAME_TIMEOUT_S,
    resolver: Callable[[str], str] | None = None,
    gateway: str | None = None,
) -> dict[str, str | None]:
    """Reverse-DNS names for ``ips``.

    With a ``gateway``, the router is asked first; otherwise the system resolver is
    used. Either way, only *local-looking* names are kept for private addresses: ISP
    DNS servers sometimes answer private-IP lookups with unrelated public names.
    Lookups run in parallel; any still running after ``timeout`` seconds count as None.
    """
    if resolver is None:
        resolver = ptr_lookup_via(gateway, timeout) if gateway else system_ptr_lookup
    ips = list(ips)
    if not ips:
        return {}
    pool = ThreadPoolExecutor(max_workers=min(HOSTNAME_WORKERS, len(ips)))
    futures = {ip: pool.submit(resolver, ip) for ip in ips}
    wait(futures.values(), timeout=timeout)
    names: dict[str, str | None] = {}
    for ip, future in futures.items():
        name = None
        if future.done() and future.exception() is None:
            name = _clean_hostname(future.result(), ip)
        names[ip] = name
    pool.shutdown(wait=False, cancel_futures=True)
    return names


def _clean_hostname(name: str, ip: str) -> str | None:
    """Normalize a PTR answer, or None if it's useless or untrustworthy.

    Drops the trailing dot, the IP echoed back as a "name", and (for private IPs)
    names outside local domains, such as an ISP's ``csp1.example.com.cn``.
    """
    name = name.strip().rstrip(".").lower()
    if not name or name == ip or name.endswith(".in-addr.arpa"):
        return None
    if ipaddress.ip_address(ip).is_private and not _looks_local(name):
        return None
    return name


def _looks_local(name: str) -> bool:
    """A single-label name (``laptop-qucl8079``) or one under a local-only suffix."""
    return "." not in name or name.endswith(LOCAL_SUFFIXES)


def scan(
    info: NetInfo,
    method: str = "auto",
    with_hostnames: bool = True,
    scapy_scan: Callable[..., dict[str, str]] = arp_scan_scapy,
    windows_scan: Callable[..., dict[str, str]] = arp_scan_windows,
) -> ScanResult:
    """Discover devices on ``info.network``.

    ``method`` is ``"auto"`` (Scapy when an Npcap interface is known, else Windows),
    ``"scapy"`` or ``"windows"``. In auto mode a Scapy failure falls back to Windows.
    This PC and the gateway are always included and flagged.
    """
    started = time.perf_counter()
    errors: list[str] = []
    found: dict[str, str] = {}
    used = method

    if method in ("auto", "scapy") and (info.pcap_iface or method == "scapy"):
        try:
            found = scapy_scan(info.network, info.pcap_iface)
            used = "scapy"
        except Exception as exc:  # noqa: BLE001 - Npcap missing, no permission, etc.
            errors.append(f"Scapy ARP scan failed ({type(exc).__name__}: {exc})")
            if method == "scapy":
                raise
    if used != "scapy":
        found = windows_scan(info.network)
        used = "windows"

    # Neither method reports this PC itself, so add it from the adapter's own details.
    if info.interface_mac:
        found.setdefault(info.local_ip, info.interface_mac)

    names = resolve_hostnames(found, gateway=info.gateway) if with_hostnames else {}
    if with_hostnames and not names.get(info.local_ip):
        names[info.local_ip] = socket.gethostname().lower()

    devices = [
        Device(
            ip=ip,
            mac=mac,
            vendor=vendors.lookup(mac),
            hostname=names.get(ip),
            is_gateway=ip == info.gateway,
            is_self=ip == info.local_ip,
        )
        for ip, mac in found.items()
    ]
    devices.sort(key=lambda d: ipaddress.ip_address(d.ip))
    return ScanResult(
        devices=devices,
        method=used,
        network=str(info.network),
        duration_ms=round((time.perf_counter() - started) * 1000),
        errors=errors,
    )
