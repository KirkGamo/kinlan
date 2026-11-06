"""Tests for the layered diagnose: one healthy run and one scenario per failing layer."""

import ipaddress
from dataclasses import replace

import pytest

from kinlan_agent import diagnose
from kinlan_agent.icmp import EchoReply
from kinlan_agent.netinfo import NetInfo

UP = EchoReply(ok=True, rtt_ms=12.0)
DOWN = EchoReply(ok=False, rtt_ms=None, status="timed out")
INFO = NetInfo(
    local_ip="192.168.1.13",
    netmask="255.255.255.0",
    network=ipaddress.ip_network("192.168.1.0/24"),
    gateway="192.168.1.1",
    interface_name="Wi-Fi",
    interface_mac="50:84:92:ee:32:66",
)


def healthy_probes(**overrides):
    probes = diagnose.Probes(
        netinfo=lambda: INFO,
        arp=lambda ip: "64:f8:8a:3a:ca:cf",
        echo=lambda ip, timeout: UP,
        dns_lookup=lambda name, server: ["93.184.215.14"],
        tcp_connect=lambda host, port, timeout: None,
        https_status=lambda url, timeout: 204,
    )
    return replace(probes, **overrides)


def statuses(result):
    return [s.status for s in result.steps]


def test_healthy_network_passes_all_six_steps():
    result = diagnose.run(healthy_probes())
    assert statuses(result) == ["pass"] * 6
    assert result.healthy and result.root_cause_step is None
    assert "working" in result.summary


def raise_(exc):
    raise exc


@pytest.mark.parametrize(
    ("overrides", "failing_step", "summary_words"),
    [
        ({"netinfo": lambda: raise_(OSError("network unreachable"))}, 1, "isn't connected"),
        ({"netinfo": lambda: replace(INFO, local_ip="169.254.7.9")}, 1, "didn't get an address"),
        ({"netinfo": lambda: replace(INFO, gateway=None)}, 1, "doesn't know where the router"),
        ({"arp": lambda ip: None}, 2, "router isn't responding"),
        ({"echo": lambda ip, t: DOWN if ip == "192.168.1.1" else UP}, 3, "weak"),
        ({"echo": lambda ip, t: UP if ip == "192.168.1.1" else DOWN}, 4, "internet provider"),
        ({"dns_lookup": lambda name, server: raise_(OSError("SERVFAIL"))}, 5, "by name"),
        ({"tcp_connect": lambda h, p, t: raise_(OSError("timed out"))}, 6, "blocking"),
        ({"https_status": lambda url, t: 302}, 6, "login page"),
    ],
)
def test_first_failing_layer_is_the_root_cause(overrides, failing_step, summary_words):
    result = diagnose.run(healthy_probes(**overrides))
    assert result.root_cause_step == failing_step
    assert statuses(result) == (
        ["pass"] * (failing_step - 1) + ["fail"] + ["skipped"] * (6 - failing_step)
    )
    assert summary_words in result.summary


def test_gateway_ping_tolerates_one_lost_echo():
    replies = iter([UP, DOWN, UP])
    echo = lambda ip, t: next(replies) if ip == "192.168.1.1" else UP  # noqa: E731
    result = diagnose.run(healthy_probes(echo=echo))
    assert result.steps[2].status == "pass"


def test_internet_passes_if_only_one_target_answers():
    echo = lambda ip, t: DOWN if ip == "8.8.8.8" else UP  # noqa: E731
    result = diagnose.run(healthy_probes(echo=echo))
    assert result.steps[3].status == "pass"


def test_dns_failure_explains_when_public_dns_works():
    def dns_lookup(name, server):
        if server is None:
            raise OSError("timed out")
        return ["93.184.215.14"]

    result = diagnose.run(healthy_probes(dns_lookup=dns_lookup))
    assert result.root_cause_step == 5
    assert "your DNS server isn't answering" in result.summary
    assert "8.8.8.8" in result.steps[4].detail


def test_every_step_has_plain_summary_and_technical_detail_when_run():
    result = diagnose.run(healthy_probes())
    for step in result.steps:
        assert step.summary and step.detail
        assert step.ms is not None


def test_to_dict_matches_command_contract():
    data = diagnose.run(healthy_probes(arp=lambda ip: None)).to_dict()
    assert data["root_cause_step"] == 2
    assert set(data["steps"][0]) == {"n", "name", "layer", "status", "ms", "summary", "detail"}
