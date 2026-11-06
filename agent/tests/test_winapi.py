"""Tests for the iphlpapi wrappers: byte-order helpers everywhere, live calls on Windows only."""

import pytest

from kinlan_agent import winapi


@pytest.mark.parametrize("ip", ["192.168.1.1", "10.0.0.254", "8.8.8.8", "0.0.0.0"])
def test_dword_round_trip(ip):
    assert winapi._from_dword(winapi._to_dword(ip)) == ip


def test_dword_is_network_byte_order():
    # iphlpapi expects the first octet in the lowest byte.
    assert winapi._to_dword("1.2.3.4") == 0x04030201


@pytest.mark.skipif(not winapi.AVAILABLE, reason="Windows only")
def test_send_arp_to_unused_test_address_returns_none():
    # 192.0.2.0/24 (TEST-NET-1) is reserved for documentation and never answers.
    assert winapi.send_arp("192.0.2.1") is None
