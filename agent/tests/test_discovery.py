"""Tests for discovery and vendor lookup. Network calls are replaced with fakes."""

import ipaddress
import time

import pytest

from kinlan_agent import discovery, vendors
from kinlan_agent.netinfo import NetInfo

NET = ipaddress.ip_network("192.168.1.0/29")  # hosts .1 to .6


def make_info(pcap_iface="\\Device\\NPF_{TEST}"):
    return NetInfo(
        local_ip="192.168.1.5",
        netmask="255.255.255.248",
        network=NET,
        gateway="192.168.1.1",
        interface_name="Wi-Fi",
        interface_mac="50:84:92:ee:32:66",
        pcap_iface=pcap_iface,
    )


# --- vendors -------------------------------------------------------------------------


def test_vendor_lookup_known_oui():
    assert vendors.lookup("50:84:92:EE:32:66") == "Intel Corporate"
    assert vendors.lookup("64-F8-8A-3A-CA-CF") == "China Mobile IOT Company Limited"


def test_vendor_lookup_randomized_mac_is_private():
    # 0xDA = 1101 1010: the locally administered bit (0b10) is set.
    assert vendors.is_randomized("da:a1:19:00:00:01")
    assert vendors.lookup("da:a1:19:00:00:01") == vendors.PRIVATE_ADDRESS


def test_vendor_lookup_unknown_and_invalid():
    assert vendors.lookup("00:00:00:00:00:00") in (None, "XEROX CORPORATION")
    assert vendors.lookup("not-a-mac") is None


def test_vendor_table_is_large():
    assert len(vendors._table()) > 30_000


# --- ARP scans -----------------------------------------------------------------------


def test_arp_scan_windows_keeps_only_answering_hosts():
    answers = {"192.168.1.1": "64-F8-8A-3A-CA-CF", "192.168.1.3": "A4:5E:60:11:22:33"}
    found = discovery.arp_scan_windows(NET, workers=4, send_arp=answers.get)
    assert found == {"192.168.1.1": "64:f8:8a:3a:ca:cf", "192.168.1.3": "a4:5e:60:11:22:33"}


def test_arp_scan_windows_skips_network_and_broadcast_addresses():
    asked = []
    discovery.arp_scan_windows(NET, workers=2, send_arp=lambda ip: asked.append(ip))
    assert sorted(asked, key=ipaddress.ip_address) == [f"192.168.1.{n}" for n in range(1, 7)]


# --- hostnames -----------------------------------------------------------------------


def test_resolve_hostnames_cleans_and_times_out():
    def resolver(ip):
        if ip == "192.168.1.1":
            return "router.home."
        if ip == "192.168.1.2":
            return "192.168.1.2"  # some DNS servers just echo the IP back
        if ip == "192.168.1.3":
            raise OSError("no PTR record")
        time.sleep(2)  # 192.168.1.4: slower than the timeout
        return "too-late"

    ips = ["192.168.1.1", "192.168.1.2", "192.168.1.3", "192.168.1.4"]
    names = discovery.resolve_hostnames(ips, timeout=0.5, resolver=resolver)
    assert names == {
        "192.168.1.1": "router.home",
        "192.168.1.2": None,
        "192.168.1.3": None,
        "192.168.1.4": None,
    }


def test_resolve_hostnames_empty():
    assert discovery.resolve_hostnames([]) == {}


# --- scan orchestration ----------------------------------------------------------------


def fake_scapy(network, iface):
    return {"192.168.1.1": "64:f8:8a:3a:ca:cf", "192.168.1.3": "da:a1:19:00:00:01"}


def test_scan_uses_scapy_when_npcap_interface_known():
    result = discovery.scan(
        make_info(),
        with_hostnames=False,
        scapy_scan=fake_scapy,
        windows_scan=lambda net: pytest.fail("Windows scan shouldn't run"),
    )
    assert result.method == "scapy"
    assert [d.ip for d in result.devices] == ["192.168.1.1", "192.168.1.3", "192.168.1.5"]
    gateway, phone, me = result.devices
    assert gateway.is_gateway and gateway.vendor == "China Mobile IOT Company Limited"
    assert phone.vendor == vendors.PRIVATE_ADDRESS
    assert me.is_self and me.mac == "50:84:92:ee:32:66"
    assert result.network == "192.168.1.0/29"


def test_scan_falls_back_to_windows_when_scapy_fails():
    def broken_scapy(network, iface):
        raise RuntimeError("Npcap not installed")

    result = discovery.scan(
        make_info(),
        with_hostnames=False,
        scapy_scan=broken_scapy,
        windows_scan=lambda net: {"192.168.1.1": "64:f8:8a:3a:ca:cf"},
    )
    assert result.method == "windows"
    assert "Npcap not installed" in result.errors[0]
    assert {d.ip for d in result.devices} == {"192.168.1.1", "192.168.1.5"}


def test_scan_without_npcap_interface_goes_straight_to_windows():
    result = discovery.scan(
        make_info(pcap_iface=None),
        with_hostnames=False,
        scapy_scan=lambda *a: pytest.fail("Scapy shouldn't run"),
        windows_scan=lambda net: {},
    )
    assert result.method == "windows"
    assert [d.ip for d in result.devices] == ["192.168.1.5"]  # this PC is always listed


def test_scan_forced_scapy_raises_instead_of_falling_back():
    def broken_scapy(network, iface):
        raise PermissionError("admin required")

    with pytest.raises(PermissionError):
        discovery.scan(make_info(), method="scapy", with_hostnames=False, scapy_scan=broken_scapy)


def test_device_to_dict():
    device = discovery.Device(ip="192.168.1.1", mac="64:f8:8a:3a:ca:cf", is_gateway=True)
    assert device.to_dict() == {
        "ip": "192.168.1.1",
        "mac": "64:f8:8a:3a:ca:cf",
        "vendor": None,
        "hostname": None,
        "is_gateway": True,
        "is_self": False,
    }


@pytest.mark.parametrize(
    ("answer", "ip", "expected"),
    [
        ("Laptop-QUCL8079.", "192.168.1.13", "laptop-qucl8079"),  # single label from router
        ("printer.lan", "192.168.1.40", "printer.lan"),  # local suffix
        ("csp1.zte.com.cn", "192.168.1.28", None),  # ISP DNS inventing a public name
        ("192.168.1.8.", "192.168.1.8", None),  # router echoing the IP back
        ("8.1.168.192.in-addr.arpa", "192.168.1.8", None),
        ("dns.google", "8.8.8.8", "dns.google"),  # public IP: public names are fine
    ],
)
def test_clean_hostname_rules(answer, ip, expected):
    assert discovery._clean_hostname(answer, ip) == expected


def test_resolve_hostnames_asks_the_gateway_when_given(monkeypatch):
    asked = {}

    def fake_ptr_via(server, timeout):
        asked["server"] = server
        return lambda ip: "phone"

    monkeypatch.setattr(discovery, "ptr_lookup_via", fake_ptr_via)
    names = discovery.resolve_hostnames(["192.168.1.16"], gateway="192.168.1.1")
    assert asked["server"] == "192.168.1.1"
    assert names == {"192.168.1.16": "phone"}
