"""Tests for the ping test. Replies are scripted, so no network is needed."""

import pytest

from kinlan_agent import pingtest
from kinlan_agent.icmp import EchoReply


def ok(ms):
    return EchoReply(ok=True, rtt_ms=ms, ttl=64)


LOST = EchoReply(ok=False, rtt_ms=None, status="timed out")


def test_summarize_matches_windows_ping_style_statistics():
    stats = pingtest.summarize("192.168.1.1", [ok(2), ok(4), LOST, ok(3), ok(7)])
    assert (stats.sent, stats.received, stats.loss_pct) == (5, 4, 20.0)
    assert (stats.min_ms, stats.avg_ms, stats.max_ms) == (2, 4.0, 7)
    # Jitter: mean |difference| between consecutive replies: (|4-2| + |3-4| + |7-3|) / 3
    assert stats.jitter_ms == pytest.approx(2.33, abs=0.01)
    assert stats.rtts_ms == (2, 4, None, 3, 7)


def test_summarize_all_lost():
    stats = pingtest.summarize("192.0.2.1", [LOST, LOST, LOST])
    assert (stats.received, stats.loss_pct) == (0, 100.0)
    assert stats.avg_ms is None and stats.jitter_ms is None and stats.min_ms is None


def test_summarize_single_reply_has_no_jitter():
    stats = pingtest.summarize("8.8.8.8", [ok(25)])
    assert stats.jitter_ms is None and stats.avg_ms == 25


def test_ping_test_sends_count_requests_with_interval_between():
    sent, slept = [], []
    replies = iter([ok(1), ok(2), ok(3)])

    def send(target, timeout_ms):
        sent.append((target, timeout_ms))
        return next(replies)

    stats = pingtest.ping_test(
        "192.168.1.1", count=3, interval_s=0.2, send=send, sleep=slept.append
    )
    assert sent == [("192.168.1.1", 1000)] * 3
    assert slept == [0.2, 0.2]  # no sleep before the first or after the last request
    assert stats.avg_ms == 2


def test_ping_test_rejects_zero_count():
    with pytest.raises(ValueError):
        pingtest.ping_test("192.168.1.1", count=0)


def test_to_dict_matches_command_contract():
    stats = pingtest.summarize("192.168.1.1", [ok(2), ok(4)])
    assert set(stats.to_dict()) == {
        "target", "sent", "received", "loss_pct", "min_ms", "avg_ms", "max_ms", "jitter_ms",
    }
