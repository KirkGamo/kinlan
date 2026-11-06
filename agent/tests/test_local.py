"""Tests for ``run --local``: the whole view runs against fake network operations."""

import io
import ipaddress
from datetime import UTC, datetime

from rich.console import Console

from kinlan_agent import diagnose, discovery, local, main, monitor
from kinlan_agent.icmp import EchoReply
from kinlan_agent.netinfo import NetInfo

INFO = NetInfo(
    local_ip="192.168.1.13",
    netmask="255.255.255.0",
    network=ipaddress.ip_network("192.168.1.0/24"),
    gateway="192.168.1.1",
    interface_name="Wi-Fi",
    interface_mac="50:84:92:ee:32:66",
    dns_servers=["192.168.1.1"],
)
SCAN = discovery.ScanResult(
    devices=[
        discovery.Device("192.168.1.1", "64:f8:8a:3a:ca:cf", "China Mobile IOT", None, True),
        discovery.Device("192.168.1.13", "50:84:92:ee:32:66", "Intel Corporate", "laptop",
                         is_self=True),
    ],
    method="scapy",
    network="192.168.1.0/24",
    duration_ms=7100,
)
UP = EchoReply(ok=True, rtt_ms=20.0)
DOWN = EchoReply(ok=False, rtt_ms=None)


def healthy_diagnosis(**_):
    steps = [diagnose.Step(n, f"Step {n}", "layer", "pass", 1.0, "fine", "ok") for n in range(1, 7)]
    return diagnose.Diagnosis(steps=steps, summary="Everything checks out.")


def make_deps(send):
    return local.LocalDeps(
        get_netinfo=lambda: INFO,
        scan=lambda info: SCAN,
        choose_targets=lambda: ["8.8.8.8", "9.9.9.9"],
        run_diagnose=healthy_diagnosis,
        send=send,
        sleep=lambda s: None,
    )


def run(send, ticks):
    out = io.StringIO()
    console = Console(file=out, width=160, force_terminal=False, color_system=None)
    session = local.run_local(ticks=ticks, console=console, deps=make_deps(send))
    return session, out.getvalue()


def test_local_view_shows_network_devices_diagnose_and_monitor():
    session, text = run(lambda ip, t: UP, ticks=3)
    assert session.ticks == 3
    for expected in ("192.168.1.0/24", "China Mobile IOT", "this PC", "Everything checks out.",
                     "Internet up", "Health: A (100/100)", "3/3"):
        assert expected in text


def test_local_view_reports_an_outage_and_lower_grade():
    send = lambda ip, t: UP if ip == "192.168.1.1" else DOWN  # noqa: E731
    session, text = run(send, ticks=4)
    assert len(session.outages) == 1 and session.open_outage.cause == "isp"
    assert "Internet DOWN since" in text
    score = session.health()
    assert score.grade in {"D", "F"}  # 100% internet loss (-30) and an outage (-5)


def test_session_counts_one_internet_result_per_tick():
    session = local.Session()
    ts = datetime(2026, 11, 20, tzinfo=UTC)
    tick = monitor.Tick(ts, True, True, [
        monitor.Sample(ts, "gateway", "192.168.1.1", 2.0, True),
        monitor.Sample(ts, "internet", "8.8.8.8", None, False),   # main target blocked
        monitor.Sample(ts, "internet", "9.9.9.9", 26.0, True),    # confirming target answered
    ])
    session.record(tick, None)
    assert (session.internet.sent, session.internet.received) == (1, 1)
    assert session.internet.avg_ms == 26.0 and session.gateway.last_ms == 2.0


def test_target_stats_loss_and_average():
    stats = local.TargetStats()
    ts = datetime(2026, 11, 20, tzinfo=UTC)
    for ok, ms in ((True, 10.0), (False, None), (True, 30.0), (True, 20.0)):
        stats.add(monitor.Sample(ts, "internet", "8.8.8.8", ms, ok))
    assert (stats.sent, stats.received, stats.avg_ms, stats.loss_pct) == (4, 3, 20.0, 25.0)
    assert stats.last_ms == 20.0


def test_cli_run_local_calls_the_local_view(monkeypatch):
    calls = {}
    monkeypatch.setattr(local, "run_local", lambda **kw: calls.update(kw))
    assert main.main(["run", "--local", "--ticks", "2", "--interval", "1"]) == 0
    assert calls == {"ticks": 2, "interval_s": 1.0}


def test_cli_run_without_local_is_not_implemented_yet(capsys):
    assert main.main(["run"]) == 2
    assert "run --local" in capsys.readouterr().err
