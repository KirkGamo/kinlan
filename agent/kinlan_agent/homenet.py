"""Which network this agent belongs to, so a PC that travels never reports another network.

A site is one network, but the PC running its agent can be a laptop. The agent remembers its
site's router by MAC address (an IP like 192.168.1.1 is the same on most home networks) and
only monitors, scans and answers commands while its default gateway is that router.

* Pairing records the network the PC is on: pairing happens on the network being added.
* A PC paired before this existed asks once, in setup or ``install``: "Is this <site>'s
  network?". Until someone says yes, the agent waits rather than guessing.
* When the router can't be identified (it's off, or the PC has no network) the agent keeps
  its last answer: at home a dead router is an outage worth recording, elsewhere it isn't.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from kinlan_agent import config, netinfo


class Where(Enum):
    HOME = "home"  # on the site's network: monitor it
    AWAY = "away"  # on another network: stay quiet
    UNKNOWN = "unknown"  # the router can't be identified right now
    UNSET = "unset"  # the site's network was never recorded


@dataclass(frozen=True)
class Network:
    cidr: str | None
    gateway: str | None
    gateway_mac: str | None

    def describe(self) -> str:
        if not self.gateway:
            return "no network"
        router = f"router {self.gateway}" + (f", {self.gateway_mac}" if self.gateway_mac else "")
        return f"{self.cidr or 'unknown subnet'} ({router})"


def _mac(value: str | None) -> str | None:
    try:
        return netinfo.normalize_mac(value) if value else None
    except ValueError:
        return None


def resolve_mac(ip: str) -> str | None:
    """The MAC address at ``ip`` on this network (an ARP request through Windows)."""
    from kinlan_agent import winapi

    return winapi.send_arp(ip)


def identify(info: netinfo.NetInfo | None, resolve: Callable[[str], str | None]) -> Network:
    """The network in ``info``, with its router's MAC asked of Windows (ARP)."""
    if info is None or not info.gateway:
        return Network(str(info.network) if info else None, None, None)
    try:
        mac = resolve(info.gateway)
    except Exception:
        mac = None
    return Network(str(info.network), info.gateway, _mac(mac))


def current(
    get_netinfo: Callable[[], netinfo.NetInfo] = netinfo.get_netinfo,
    resolve: Callable[[str], str | None] = resolve_mac,
) -> Network:
    try:
        info = get_netinfo()
    except Exception:
        info = None
    return identify(info, resolve)


def where(settings: config.AgentConfig, net: Network) -> Where:
    home = _mac(settings.home_gateway_mac)
    if not home:
        return Where.UNSET
    if not net.gateway_mac:
        return Where.UNKNOWN
    return Where.HOME if net.gateway_mac == home else Where.AWAY


def remember(net: Network) -> None:
    """Record ``net`` as this site's network in config.toml."""
    settings = config.load()
    settings.home_gateway_mac, settings.home_network = net.gateway_mac, net.cidr
    config.save(settings)


def home_description(settings: config.AgentConfig) -> str:
    if not settings.home_gateway_mac:
        return "not recorded yet"
    return f"{settings.home_network or 'unknown subnet'} (router {settings.home_gateway_mac})"


def confirm(
    ask: Callable[[str], str] = input,
    say: Callable[[str], None] = print,
    net: Network | None = None,
) -> bool:
    """For a PC paired before the network was recorded: ask whether this is the site's network.
    Returns True when the network is (now) recorded."""
    settings = config.load()
    if settings.home_gateway_mac:
        return True
    net = net or current()
    site = settings.site_name or "this site"
    if not net.gateway_mac:
        say(f"Can't identify this network's router, so KinLAN can't tell if it's {site}'s.")
        say("The agent will wait. Run KinLAN-Agent.exe again once this PC is on that network.")
        return False
    say(f"This PC is on {net.describe()}.")
    if ask(f'Is this {site}\'s network? Type "yes" or "no": ').strip().lower() == "yes":
        remember(net)
        say(f"Recorded. The agent monitors {site} only while this PC is on this network.")
        return True
    say(f"Not recorded. The agent waits, and monitors nothing, until this is answered on {site}'s")
    say("network: run KinLAN-Agent.exe again there.")
    return False
