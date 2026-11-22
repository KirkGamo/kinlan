"""The risky-port check (#89) with fake connections: no real network is touched."""

import asyncio
from datetime import datetime, timedelta, timezone

from kinlan_agent import portcheck
from kinlan_agent.buffer import Buffer
from kinlan_agent.runner import seconds_until
from kinlan_agent.uploader import Batch, build_payload

PC = portcheck.Target("50:84:92:00:00:02", "192.168.1.13")
NAS = portcheck.Target("00:11:32:00:00:07", "192.168.1.30")
ROUTER = portcheck.Target("64:f8:8a:00:00:01", "192.168.1.1")


def answers(*open_):
    """A fake network where only these (ip, port) pairs answer; records every attempt."""
    tried = []

    async def opener(ip, port, timeout):
        tried.append((ip, port, timeout))
        return (ip, port) in open_

    return opener, tried


def test_open_ports_are_reported_per_device_with_their_service():
    opener, tried = answers(("192.168.1.30", 445), ("192.168.1.1", 23), ("192.168.1.1", 80))
    result = portcheck.check([NAS, ROUTER], opener=opener)
    assert result.open == [  # sorted by device, then port
        {"mac": NAS.mac, "port": 445, "service": "smb"},
        {"mac": ROUTER.mac, "port": 23, "service": "telnet"},
        {"mac": ROUTER.mac, "port": 80, "service": "http"},
    ]
    assert result.macs == [NAS.mac, ROUTER.mac]
    assert result.ports == [21, 23, 80, 445, 3389, 5900, 8080]
    assert len(tried) == 2 * 7 and {t for _, _, t in tried} == {0.5}


def test_the_agents_own_pc_is_skipped():
    opener, tried = answers(("192.168.1.13", 445))
    result = portcheck.check([PC, ROUTER], skip_ip="192.168.1.13", opener=opener)
    assert result.macs == [ROUTER.mac] and result.open == []
    assert all(ip != "192.168.1.13" for ip, _, _ in tried)


def test_no_more_than_the_limit_run_at_once():
    running = peak = 0

    async def opener(ip, port, timeout):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.001)
        running -= 1
        return False

    many = [portcheck.Target(f"02:00:00:00:00:{i:02x}", f"192.168.1.{i}") for i in range(2, 60)]
    portcheck.check(many, concurrency=100, opener=opener)
    assert peak == 100


def test_a_real_closed_port_reads_as_closed_quickly():
    """Nothing listens on port 9 of the loopback address: refused at once, not a timeout."""
    assert asyncio.run(portcheck.tcp_open("127.0.0.1", 9, 0.5)) is False


def test_the_result_has_what_the_server_expects():
    opener, _ = answers(("192.168.1.30", 3389))
    d = portcheck.check([NAS], opener=opener).to_dict()
    assert set(d) == {"checked_at", "ports", "macs", "open", "duration_ms"}
    assert d["checked_at"].endswith("Z")


def test_the_daily_check_waits_for_the_next_three_oclock():
    tz = timezone(timedelta(hours=8))
    assert seconds_until("03:00", datetime(2026, 11, 22, 2, 0, tzinfo=tz)) == 3600
    assert seconds_until("03:00", datetime(2026, 11, 22, 3, 0, tzinfo=tz)) == 24 * 3600
    assert seconds_until("nonsense", datetime(2026, 11, 22, 4, 0, tzinfo=tz)) == 23 * 3600


def test_scheduled_checks_upload_as_port_checks():
    with Buffer(":memory:") as buffer:
        opener, _ = answers()
        buffer.add("port_check", portcheck.check([NAS], opener=opener).to_dict())
        payload = build_payload(Batch("b-1", buffer.peek()), version="0.1.0")
    [item] = payload["port_checks"]
    assert item["macs"] == [NAS.mac] and item["open"] == []
