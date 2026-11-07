"""The cloud runner: monitor ticks into the outbox, outages, scans and commands (with fakes)."""

import ipaddress
from datetime import UTC, datetime

import httpx
import pytest

from kinlan_agent import diagnose, discovery, netinfo, pingtest
from kinlan_agent.buffer import Buffer
from kinlan_agent.config import AgentConfig
from kinlan_agent.icmp import EchoReply
from kinlan_agent.runner import CloudDeps, CommandPoller, Runtime, execute

INFO = netinfo.NetInfo(
    local_ip="192.168.1.13",
    netmask="255.255.255.0",
    network=ipaddress.IPv4Network("192.168.1.0/24"),
    gateway="192.168.1.1",
    interface_name="Wi-Fi",
    interface_mac="50:84:92:00:00:02",
)


class Net:
    """A fake network whose internet can be switched off."""

    def __init__(self):
        self.internet_up = True

    def send(self, ip: str, timeout_ms: int) -> EchoReply:
        if ip == "192.168.1.1":
            return EchoReply(ok=True, rtt_ms=2.0)
        return EchoReply(ok=self.internet_up, rtt_ms=20.0 if self.internet_up else None)


def deps(net: Net, diagnoses: list | None = None) -> CloudDeps:
    def fake_diagnose(**_):
        result = diagnose.Diagnosis(steps=[], root_cause_step=4, summary="Provider down")
        if diagnoses is not None:
            diagnoses.append(result)
        return result

    return CloudDeps(
        get_netinfo=lambda **_: INFO,
        scan=lambda info: discovery.ScanResult(
            devices=[discovery.Device("192.168.1.1", "64:f8:8a:00:00:01", "ZTE", None, True)],
            method="windows",
            network=str(info.network),
            duration_ms=50,
        ),
        choose_targets=lambda candidates, send: ["8.8.8.8", "9.9.9.9"],
        run_diagnose=fake_diagnose,
        ping_test=lambda ip, count, send: pingtest.summarize(ip, [send(ip, 1000)] * count),
        send=net.send,
    )


@pytest.fixture
def buffer():
    with Buffer(":memory:") as b:
        yield b


def test_ticks_queue_samples(buffer):
    rt = Runtime(AgentConfig(), buffer, deps(Net()))
    rt.start()
    rt.tick()
    kinds = [i.kind for i in buffer.peek()]
    assert kinds == ["sample", "sample"]  # gateway + main internet target


def test_an_outage_is_recorded_diagnosed_and_queued_when_it_ends(buffer):
    net, diagnoses = Net(), []
    rt = Runtime(AgentConfig(), buffer, deps(net, diagnoses))
    rt.start()
    net.internet_up = False
    for _ in range(3):
        rt.tick()
    assert buffer.current_outage() is not None and buffer.current_outage().cause == "isp"
    assert len(diagnoses) == 1
    net.internet_up = True
    for _ in range(2):
        rt.tick()
    outages = [i.payload for i in buffer.peek(100) if i.kind == "outage"]
    assert len(outages) == 1 and outages[0]["cause"] == "isp" and outages[0]["ended_at"]
    assert buffer.current_outage() is None


def test_an_outage_open_before_a_restart_keeps_its_start_time(buffer):
    started = datetime(2026, 11, 20, 9, 41, tzinfo=UTC)
    buffer.open_outage(started, "isp")
    rt = Runtime(AgentConfig(), buffer, deps(Net()))
    rt.start()
    for _ in range(2):
        rt.tick()
    outage = next(i.payload for i in buffer.peek(100) if i.kind == "outage")
    assert outage["started_at"].startswith("2026-11-20T09:41")


def test_scan_queues_devices_with_the_netinfo(buffer):
    rt = Runtime(AgentConfig(), buffer, deps(Net()))
    rt.start()
    rt.scan_now()
    item = buffer.peek()[0]
    assert item.kind == "scan" and item.payload["netinfo"]["gateway"] == "192.168.1.1"
    assert item.payload["devices"][0]["mac"] == "64:f8:8a:00:00:01"


@pytest.mark.parametrize(
    ("command", "ok", "check"),
    [
        ({"type": "scan"}, True, lambda r: r["devices"][0]["is_gateway"] is True),
        (
            {"type": "ping_test", "params": {"ip": "192.168.1.1", "count": 3}},
            True,
            lambda r: (r["sent"], r["received"]) == (3, 3),
        ),
        ({"type": "diagnose"}, True, lambda r: r["root_cause_step"] == 4),
        ({"type": "ping_test", "params": {}}, False, None),
        ({"type": "port_check"}, False, None),
        ({"type": "reboot"}, False, None),
    ],
)
def test_commands(buffer, command, ok, check):
    rt = Runtime(AgentConfig(), buffer, deps(Net()))
    rt.start()
    got_ok, result, error = execute(command, rt)
    assert got_ok is ok
    if ok:
        assert check(result) and error is None
    else:
        assert result is None and error


def test_poller_runs_commands_and_reports_results(buffer):
    rt = Runtime(AgentConfig(), buffer, deps(Net()))
    rt.start()
    reported = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.params["wait"] == "0"
            return httpx.Response(200, json={"commands": [{"id": "c-1", "type": "diagnose"}]})
        reported["url"] = str(request.url)
        reported["body"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={})

    poller = CommandPoller(
        rt,
        "https://api.example",
        "tok",
        wait_s=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert poller.poll_once() is True
    assert reported["url"].endswith("/api/v1/agent/commands/c-1/result")
    assert reported["body"]["ok"] is True and reported["body"]["result"]["root_cause_step"] == 4
