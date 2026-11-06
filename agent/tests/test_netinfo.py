"""Tests for netinfo. Helpers use fake data; the live smoke test skips without a network."""

import ipaddress
import socket
from types import SimpleNamespace

import psutil
import pytest

from kinlan_agent import netinfo


def _addr(family, address, netmask=None):
    return SimpleNamespace(family=family, address=address, netmask=netmask)


FAKE_ADDRS = {
    "vEthernet (WSL)": [_addr(socket.AF_INET, "172.20.0.1", "255.255.240.0")],
    "Wi-Fi": [
        _addr(psutil.AF_LINK, "A4-5E-60-11-22-33"),
        _addr(socket.AF_INET, "192.168.1.13", "255.255.255.0"),
    ],
}


def test_find_interface_picks_adapter_with_the_outbound_ip():
    assert netinfo.find_interface("192.168.1.13", FAKE_ADDRS) == (
        "Wi-Fi",
        "255.255.255.0",
        "a4:5e:60:11:22:33",
    )


def test_find_interface_raises_for_unknown_ip():
    with pytest.raises(LookupError):
        netinfo.find_interface("10.0.0.5", FAKE_ADDRS)


@pytest.mark.parametrize(
    ("ip", "mask", "expected"),
    [
        ("192.168.1.13", "255.255.255.0", "192.168.1.0/24"),
        ("192.168.4.77", "255.255.252.0", "192.168.4.0/22"),  # /22 is still scanned whole
        ("10.20.30.40", "255.255.0.0", "10.20.30.0/24"),  # /16 is too wide: host's /24 only
    ],
)
def test_scan_network_limits_wide_subnets(ip, mask, expected):
    assert netinfo.scan_network(ip, mask) == ipaddress.ip_network(expected)


@pytest.mark.parametrize(
    ("ip", "expected"), [("169.254.10.3", True), ("192.168.1.13", False)]
)
def test_is_apipa(ip, expected):
    assert netinfo.is_apipa(ip) is expected


@pytest.mark.parametrize(
    "raw", ["A4-5E-60-11-22-33", "a4:5e:60:11:22:33", "A45E.6011.2233", "a45e60112233"]
)
def test_normalize_mac_accepts_common_formats(raw):
    assert netinfo.normalize_mac(raw) == "a4:5e:60:11:22:33"


@pytest.mark.parametrize("raw", ["", "a4:5e:60", "zz:5e:60:11:22:33"])
def test_normalize_mac_rejects_invalid(raw):
    with pytest.raises(ValueError):
        netinfo.normalize_mac(raw)


def test_netinfo_to_dict_is_json_friendly():
    info = netinfo.NetInfo(
        local_ip="192.168.1.13",
        netmask="255.255.255.0",
        network=ipaddress.ip_network("192.168.1.0/24"),
        gateway="192.168.1.1",
        interface_name="Wi-Fi",
        interface_mac="a4:5e:60:11:22:33",
        dns_servers=["8.8.8.8"],
    )
    assert info.to_dict() == {
        "local_ip": "192.168.1.13",
        "cidr": "192.168.1.0/24",
        "gateway": "192.168.1.1",
        "interface": "Wi-Fi",
        "dns_servers": ["8.8.8.8"],
    }
    assert info.is_apipa is False


def test_get_netinfo_on_this_machine():
    try:
        netinfo.outbound_ip()
    except OSError:
        pytest.skip("no network route on this machine")
    info = netinfo.get_netinfo()
    assert ipaddress.ip_address(info.local_ip) in info.network
    assert info.interface_name


def test_default_gateway_prefers_windows_route(monkeypatch):
    monkeypatch.setattr(netinfo.winapi, "best_route_next_hop", lambda dest: "192.168.1.1")
    monkeypatch.setattr(netinfo, "_scapy_route", lambda: pytest.fail("Scapy shouldn't be used"))
    assert netinfo.default_gateway() == "192.168.1.1"


def test_default_gateway_falls_back_to_scapy(monkeypatch):
    monkeypatch.setattr(netinfo.winapi, "best_route_next_hop", lambda dest: None)
    monkeypatch.setattr(netinfo, "_scapy_route", lambda: ("eth0", "10.0.0.1"))
    assert netinfo.default_gateway() == "10.0.0.1"


def test_default_gateway_none_without_any_route(monkeypatch):
    monkeypatch.setattr(netinfo.winapi, "best_route_next_hop", lambda dest: None)
    monkeypatch.setattr(netinfo, "_scapy_route", lambda: (None, None))
    assert netinfo.default_gateway() is None
