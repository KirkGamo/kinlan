"""Tests for the monitor: target choice, per-tick sampling and the outage state machine."""

from datetime import UTC, datetime, timedelta

import pytest

from kinlan_agent import monitor
from kinlan_agent.icmp import EchoReply

T0 = datetime(2026, 11, 20, 10, 0, 0, tzinfo=UTC)
UP = EchoReply(ok=True, rtt_ms=20.0)
DOWN = EchoReply(ok=False, rtt_ms=None, status="timed out")


def tick(n, internet_ok, gateway_ok=True):
    return monitor.Tick(ts=T0 + timedelta(seconds=10 * n), gateway_ok=gateway_ok,
                        internet_ok=internet_ok)


# --- choose_internet_targets ----------------------------------------------------------


def test_choose_targets_skips_blocked_candidates():
    blocked = {"8.8.8.8"}
    send = lambda ip, t: DOWN if ip in blocked else UP  # noqa: E731
    assert monitor.choose_internet_targets(send=send) == ["9.9.9.9", "1.1.1.1"]


def test_choose_targets_counts_a_candidate_that_answers_on_the_second_attempt():
    replies = {"8.8.8.8": iter([DOWN, UP])}
    send = lambda ip, t: next(replies[ip]) if ip in replies else UP  # noqa: E731
    assert monitor.choose_internet_targets(send=send) == ["8.8.8.8", "9.9.9.9"]


def test_choose_targets_falls_back_to_defaults_when_nothing_answers():
    targets = monitor.choose_internet_targets(send=lambda ip, t: DOWN)
    assert targets == ["8.8.8.8", "9.9.9.9"]


# --- OutageDetector ----------------------------------------------------------------------


def test_outage_starts_after_three_failing_ticks_with_first_failure_time():
    d = monitor.OutageDetector()
    assert d.update(tick(0, True)) is None
    assert d.update(tick(1, False)) is None
    assert d.update(tick(2, False)) is None
    event = d.update(tick(3, False))
    assert event.kind == "started"
    assert event.outage.started_at == T0 + timedelta(seconds=10)  # first failing tick
    assert event.outage.cause == "isp"  # the gateway still answered


def test_short_blip_is_not_an_outage():
    d = monitor.OutageDetector()
    events = [d.update(tick(n, ok)) for n, ok in enumerate([False, False, True, False, True])]
    assert events == [None] * 5 and d.current is None


def test_outage_cause_is_lan_when_gateway_is_also_down():
    d = monitor.OutageDetector()
    for n in range(3):
        event = d.update(tick(n, False, gateway_ok=False))
    assert event.outage.cause == "lan"


def test_outage_ends_after_two_good_ticks_with_first_good_time():
    d = monitor.OutageDetector()
    for n in range(3):
        d.update(tick(n, False))
    assert d.update(tick(3, False)) is None  # still down
    assert d.update(tick(4, True)) is None  # one good tick isn't enough
    assert d.update(tick(5, False)) is None  # relapse resets recovery
    assert d.update(tick(6, True)) is None
    event = d.update(tick(7, True))
    assert event.kind == "ended"
    assert event.outage.ended_at == T0 + timedelta(seconds=60)
    assert event.outage.duration_s == 60.0
    assert d.current is None


def test_outage_to_dict_uses_utc_z_times():
    outage = monitor.Outage(started_at=T0, cause="isp", ended_at=T0 + timedelta(minutes=4))
    assert outage.to_dict() == {
        "started_at": "2026-11-20T10:00:00Z",
        "ended_at": "2026-11-20T10:04:00Z",
        "cause": "isp",
    }


# --- Monitor.tick --------------------------------------------------------------------------


class ScriptedNetwork:
    def __init__(self, down=()):
        self.down = set(down)
        self.asked = []

    def __call__(self, ip, timeout_ms):
        self.asked.append(ip)
        return DOWN if ip in self.down else UP


def make_monitor(network, gateway="192.168.1.1"):
    return monitor.Monitor(gateway, ["8.8.8.8", "9.9.9.9"], send=network, clock=lambda: T0)


def test_tick_pings_gateway_and_primary_only_when_healthy():
    net = ScriptedNetwork()
    t, event = make_monitor(net).tick()
    assert net.asked == ["192.168.1.1", "8.8.8.8"]
    assert (t.gateway_ok, t.internet_ok, event) == (True, True, None)
    assert [s.target for s in t.samples] == ["gateway", "internet"]


def test_tick_asks_confirming_target_when_primary_fails():
    net = ScriptedNetwork(down={"8.8.8.8"})
    t, _ = make_monitor(net).tick()
    assert net.asked == ["192.168.1.1", "8.8.8.8", "9.9.9.9"]
    assert t.internet_ok is True  # one blocked server isn't an outage


def test_three_bad_ticks_report_an_isp_outage():
    m = make_monitor(ScriptedNetwork(down={"8.8.8.8", "9.9.9.9"}))
    events = [m.tick()[1] for _ in range(3)]
    assert events[:2] == [None, None]
    assert events[2].kind == "started" and events[2].outage.cause == "isp"


def test_tick_without_gateway():
    net = ScriptedNetwork()
    t, _ = make_monitor(net, gateway=None).tick()
    assert t.gateway_ok is None and net.asked == ["8.8.8.8"]


def test_monitor_requires_two_internet_targets():
    with pytest.raises(ValueError):
        monitor.Monitor("192.168.1.1", ["8.8.8.8"])


def test_sample_to_dict():
    s = monitor.Sample(T0, "internet", "8.8.8.8", 18.4, True)
    assert s.to_dict() == {"ts": "2026-11-20T10:00:00Z", "target": "internet",
                           "ip": "8.8.8.8", "rtt_ms": 18.4, "ok": True}
