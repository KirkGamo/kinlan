"""The layered troubleshooter: find which network layer failed.

Six checks run in order, from the PC's own adapter outward to the web. The first one
that fails is the root cause, and the rest are reported as skipped. Each step carries a
plain-language ``summary`` (shown first in the app) and a technical ``detail`` (shown on
tap), as PRODUCT.md requires.

| # | Check | Layer |
|---|-------|-------|
| 1 | Adapter is up with a non-APIPA IPv4 address | Physical / data link |
| 2 | The gateway's MAC address resolves with ARP | Data link |
| 3 | The gateway answers ping (3 echoes, at most 1 lost) | Network (LAN) |
| 4 | Either internet target answers ping (3 echoes each) | Network (WAN) |
| 5 | The PC's DNS servers resolve a name | Application (DNS) |
| 6 | TCP to port 443, then an HTTPS request, both work | Transport / application |

See docs/KinLAN_Technical_Plan.md, Section 3.3.
"""

from __future__ import annotations

import socket
import time
from collections.abc import Callable
from dataclasses import dataclass

from kinlan_agent import netinfo as netinfo_mod
from kinlan_agent import winapi
from kinlan_agent.icmp import EchoReply, echo
from kinlan_agent.monitor import DEFAULT_INTERNET_CANDIDATES

DNS_TEST_NAME = "example.com"
HTTPS_PROBE_URL = "https://www.google.com/generate_204"  # answers 204 with no body
ECHOES = 3


@dataclass
class Step:
    """One diagnose step and its outcome."""

    n: int
    name: str
    layer: str
    status: str = "skipped"  # "pass", "fail" or "skipped"
    ms: float | None = None
    summary: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "name": self.name,
            "layer": self.layer,
            "status": self.status,
            "ms": self.ms,
            "summary": self.summary,
            "detail": self.detail,
        }


@dataclass
class Diagnosis:
    """All six steps and the root cause, if any."""

    steps: list[Step]
    root_cause_step: int | None = None
    summary: str = ""

    @property
    def healthy(self) -> bool:
        return self.root_cause_step is None

    def to_dict(self) -> dict[str, object]:
        """Matches the ``diagnose`` command result contract (plan, Section 4.3)."""
        return {
            "steps": [s.to_dict() for s in self.steps],
            "root_cause_step": self.root_cause_step,
            "summary": self.summary,
        }


def _dns_lookup(name: str, server: str | None = None) -> list[str]:
    """Resolve ``name`` to IPv4 addresses, through ``server`` or the system's DNS servers."""
    import dns.resolver

    resolver = dns.resolver.Resolver(configure=server is None)
    if server:
        resolver.nameservers = [server]
    resolver.lifetime = 3.0
    return [str(a) for a in resolver.resolve(name, "A")]


def _tcp_connect(host: str, port: int, timeout: float) -> None:
    socket.create_connection((host, port), timeout=timeout).close()


def _https_status(url: str, timeout: float) -> int:
    import httpx

    return httpx.get(url, timeout=timeout, follow_redirects=False).status_code


@dataclass
class Probes:
    """The network operations diagnose needs; tests replace them with fakes."""

    netinfo: Callable[[], netinfo_mod.NetInfo] = netinfo_mod.get_netinfo
    arp: Callable[[str], str | None] = winapi.send_arp
    echo: Callable[[str, int], EchoReply] = echo
    dns_lookup: Callable[[str, str | None], list[str]] = _dns_lookup
    tcp_connect: Callable[[str, int, float], None] = _tcp_connect
    https_status: Callable[[str, float], int] = _https_status


def _timed(fn: Callable[[], object]) -> tuple[object, float]:
    started = time.perf_counter()
    result = fn()
    return result, round((time.perf_counter() - started) * 1000, 1)


def _echoes(probes: Probes, ip: str) -> list[EchoReply]:
    return [probes.echo(ip, 1000) for _ in range(ECHOES)]


def _replies(replies: list[EchoReply]) -> str:
    ok = [r.rtt_ms for r in replies if r.ok]
    text = f"{len(ok)} of {len(replies)} replies"
    if ok:
        text += f", average {sum(ok) / len(ok):.0f} ms"
    return text


def run(
    probes: Probes | None = None,
    internet_targets: tuple[str, str] = DEFAULT_INTERNET_CANDIDATES[:2],
) -> Diagnosis:
    """Run the six steps in order and stop at the first failure."""
    probes = probes or Probes()
    steps = [
        Step(1, "Network adapter", "Physical / data link"),
        Step(2, "Router reachable (ARP)", "Data link"),
        Step(3, "Router answers ping", "Network (LAN)"),
        Step(4, "Internet answers ping", "Network (WAN)"),
        Step(5, "Name lookup (DNS)", "Application (DNS)"),
        Step(6, "Secure web connection", "Transport / application"),
    ]
    info = None

    def check_adapter(step: Step) -> bool:
        nonlocal info
        try:
            info, step.ms = _timed(probes.netinfo)
        except (OSError, LookupError) as exc:
            step.summary = "This PC isn't connected to a network."
            step.detail = f"No usable IPv4 route or adapter: {exc}. Check the cable or Wi-Fi."
            return False
        if info.is_apipa:
            step.summary = "This PC is connected but didn't get an address from the router."
            step.detail = (f"{info.interface_name} has self-assigned address {info.local_ip} "
                           "(169.254.x.x, APIPA): DHCP failed. Restart the router or reconnect.")
            return False
        if not info.gateway:
            step.summary = "This PC is connected but doesn't know where the router is."
            step.detail = f"{info.interface_name} ({info.local_ip}) has no default gateway."
            return False
        step.summary = "This PC is connected to the network."
        step.detail = (f"{info.interface_name}: {info.local_ip} on {info.network}, "
                       f"gateway {info.gateway}.")
        return True

    def check_arp(step: Step) -> bool:
        mac, step.ms = _timed(lambda: probes.arp(info.gateway))
        if not mac:
            step.summary = "The router isn't responding on this network."
            step.detail = (f"No ARP reply from gateway {info.gateway}. This PC may be on the wrong "
                           "Wi-Fi network or VLAN, or the router is off.")
            return False
        step.summary = "The router is on the network."
        step.detail = f"ARP: {info.gateway} is at {mac}."
        return True

    def check_gateway_ping(step: Step) -> bool:
        replies, step.ms = _timed(lambda: _echoes(probes, info.gateway))
        lost = sum(not r.ok for r in replies)
        detail = f"ICMP echo to {info.gateway}: {_replies(replies)}."
        step.detail = detail
        if lost > 1:
            step.summary = "The connection to your router is weak or the router is overloaded."
            step.detail += " Move closer to the router, or restart it."
            return False
        step.summary = "Your router is responding normally."
        return True

    def check_internet_ping(step: Step) -> bool:
        results = {}
        started = time.perf_counter()
        for ip in internet_targets:
            results[ip] = _echoes(probes, ip)
        step.ms = round((time.perf_counter() - started) * 1000, 1)
        step.detail = "; ".join(f"ICMP echo to {ip}: {_replies(r)}" for ip, r in results.items())
        if not any(r.ok for replies in results.values() for r in replies):
            step.summary = "Your router is fine, but your internet provider isn't responding."
            step.detail += ". The problem is between your router and the internet (ISP outage)."
            return False
        step.summary = "The internet is reachable."
        return True

    def check_dns(step: Step) -> bool:
        try:
            addresses, step.ms = _timed(lambda: probes.dns_lookup(DNS_TEST_NAME, None))
        except Exception as exc:  # noqa: BLE001 - any resolver failure fails this step
            step.detail = f"Lookup of {DNS_TEST_NAME} with this PC's DNS servers failed: {exc}."
            public = internet_targets[0]
            try:
                probes.dns_lookup(DNS_TEST_NAME, public)
                step.summary = ("The internet works, but your DNS server isn't answering, "
                                "so websites won't load by name.")
                step.detail += (f" The public DNS server {public} answered, so switching the "
                                f"PC or router to {public} or {internet_targets[1]} fixes it.")
            except Exception:  # noqa: BLE001
                step.summary = "Websites can't be found by name (DNS isn't working)."
            return False
        step.summary = "Website names are found normally."
        step.detail = f"{DNS_TEST_NAME} resolved to {', '.join(addresses)}."
        return True

    def check_https(step: Step) -> bool:
        host = internet_targets[0]
        try:
            _, tcp_ms = _timed(lambda: probes.tcp_connect(host, 443, 3.0))
        except OSError as exc:
            step.summary = "Something is blocking secure web connections."
            step.detail = f"TCP connect to {host}:443 failed: {exc}. A firewall may be blocking it."
            return False
        try:
            status, https_ms = _timed(lambda: probes.https_status(HTTPS_PROBE_URL, 5.0))
        except Exception as exc:  # noqa: BLE001
            step.summary = "Secure websites aren't loading."
            step.detail = f"TCP to {host}:443 worked ({tcp_ms} ms), but HTTPS failed: {exc}."
            return False
        step.ms = round(tcp_ms + https_ms, 1)
        if status != 204:
            step.summary = "A login page or filter is intercepting web traffic."
            step.detail = (f"{HTTPS_PROBE_URL} returned HTTP {status} instead of 204, which "
                           "usually means a captive portal (Wi-Fi sign-in page) or a web filter.")
            return False
        step.summary = "Secure websites load normally."
        step.detail = (f"TCP {host}:443 in {tcp_ms} ms; "
                       f"HTTPS {HTTPS_PROBE_URL} returned 204 in {https_ms} ms.")
        return True

    checks = [check_adapter, check_arp, check_gateway_ping, check_internet_ping, check_dns,
              check_https]
    diagnosis = Diagnosis(steps=steps)
    for step, check in zip(steps, checks, strict=True):
        if check(step):
            step.status = "pass"
            continue
        step.status = "fail"
        diagnosis.root_cause_step = step.n
        diagnosis.summary = step.summary
        for later in steps[step.n:]:
            later.summary = "Skipped because an earlier step failed."
        return diagnosis
    diagnosis.summary = "Everything checks out: your network and internet are working."
    return diagnosis
