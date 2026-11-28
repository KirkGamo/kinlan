"""The agent only measures its site's network, even when its PC is a laptop that travels."""

import ipaddress
from dataclasses import replace
from datetime import timedelta

import pytest

from kinlan_agent import config, homenet
from kinlan_agent.buffer import Buffer
from kinlan_agent.config import AgentConfig
from kinlan_agent.homenet import Network, Where
from kinlan_agent.runner import HOLD_DOUBTFUL_S, Runtime, execute
from tests.test_runner import INFO, ROUTER, Net, at_home, deps

SCHOOL = replace(
    INFO,
    local_ip="10.124.37.236",
    network=ipaddress.IPv4Network("10.124.36.0/22"),
    gateway="10.124.36.1",
)
SCHOOL_ROUTER = "00:1a:2b:3c:4d:5e"


class Laptop:
    """Fakes for a PC that can be carried between networks (or lose its router)."""

    def __init__(self):
        self.info, self.router_answers = INFO, True

    def go(self, info):
        self.info = info

    def get_netinfo(self, **_):
        return self.info

    def route(self):
        return self.info.local_ip, self.info.gateway

    def gateway_mac(self, ip):
        if not self.router_answers:
            return None
        return {"192.168.1.1": ROUTER, "10.124.36.1": SCHOOL_ROUTER}.get(ip)


@pytest.fixture
def buffer():
    with Buffer(":memory:") as b:
        yield b


def runtime(buffer, laptop, net=None, settings=None):
    d = deps(net or Net())
    d.get_netinfo, d.gateway_mac, d.route = laptop.get_netinfo, laptop.gateway_mac, laptop.route
    settings = settings or at_home()
    d.load_config = lambda: settings
    return Runtime(settings, buffer, d)


def test_the_router_mac_decides_not_its_ip():
    home = at_home()
    assert homenet.where(home, Network("192.168.1.0/24", "192.168.1.1", ROUTER)) is Where.HOME
    # Another network with the same, very common, addresses is still another network.
    other = Network("192.168.1.0/24", "192.168.1.1", "aa:aa:aa:aa:aa:aa")
    assert homenet.where(home, other) is Where.AWAY
    assert homenet.where(home, Network("192.168.1.0/24", "192.168.1.1", None)) is Where.UNKNOWN
    assert homenet.where(AgentConfig(), other) is Where.UNSET
    typed = AgentConfig(home_gateway_mac="64-F8-8A-00-00-01")  # edited by hand
    assert homenet.where(typed, Network(None, "192.168.1.1", ROUTER)) is Where.HOME
    assert homenet.where(AgentConfig(home_gateway_mac="router"), other) is Where.UNSET


def test_on_another_network_the_agent_measures_nothing(buffer):
    laptop = Laptop()
    laptop.go(SCHOOL)
    rt = runtime(buffer, laptop)
    rt.start()
    assert rt.where is Where.AWAY and not rt.active
    rt.tick()
    rt.daily_port_check()
    assert buffer.count() == 0
    ok, result, error = execute({"type": "scan"}, rt)
    assert not ok and result is None
    assert "isn't on Home's network" in error and "10.124.36.0/22" in error


def test_it_starts_when_the_pc_comes_home_and_stops_when_it_leaves(buffer):
    laptop, net = Laptop(), Net()
    laptop.go(SCHOOL)
    rt = runtime(buffer, laptop, net)
    rt.start()
    laptop.go(INFO)
    assert rt.check_network() is Where.HOME
    rt.tick()
    assert buffer.count() == 2  # gateway + internet samples

    # Leaving: the router stops answering before the PC joins the next network, which looks
    # like an outage from inside. It was the PC that left, so nothing is kept.
    net.internet_up, laptop.router_answers = False, False
    for _ in range(3):
        rt.tick()
    assert buffer.current_outage() is not None
    assert rt.check_network() is Where.HOME  # router silent: keep the last answer
    laptop.router_answers = True
    laptop.go(SCHOOL)
    assert rt.check_network() is Where.AWAY
    assert buffer.current_outage() is None
    # Nothing measured while leaving reaches the site: no failed pings, outage or diagnose
    # (seen Nov 26: "Router not responding" stuck in the app after switching to a hotspot).
    assert [i.kind for i in buffer.peek(100)] == ["sample", "sample"]
    assert all(i.payload["ok"] for i in buffer.peek(100))


def test_a_network_switch_is_noticed_before_the_next_measurement(buffer):
    """On the new network 192.168.1.1 may answer too (a carrier's device, 192 ms through a phone
    hotspot on Nov 26). The changed route is noticed at the next tick, before any ping."""
    laptop = Laptop()
    rt = runtime(buffer, laptop)
    rt.start()
    rt.tick()
    assert buffer.count() == 2
    laptop.go(SCHOOL)  # between the minute checks
    rt.tick()
    assert rt.where is Where.AWAY and buffer.count() == 2  # nothing measured on the hotspot
    laptop.go(INFO)
    rt.check_network()
    rt.tick()
    assert buffer.count() == 4


def test_a_dead_router_at_home_is_still_an_outage(buffer):
    laptop, net = Laptop(), Net()
    rt = runtime(buffer, laptop, net)
    rt.start()
    net.internet_up, laptop.router_answers = False, False
    for _ in range(3):
        rt.tick()
    assert rt.check_network() is Where.HOME and buffer.current_outage() is not None
    assert buffer.count() == 0  # held: it could still be the PC leaving
    # Two minutes on, with still no router, it's the network: everything held is sent.
    rt.held_since -= timedelta(seconds=HOLD_DOUBTFUL_S + 1)
    rt.tick()
    kinds = [i.kind for i in buffer.peek(100)]
    assert kinds.count("sample") == 12 and kinds.count("diagnose") == 1  # 4 ticks x 3 pings


def test_a_provider_outage_isnt_held_because_the_router_answers(buffer):
    laptop, net = Laptop(), Net()
    rt = runtime(buffer, laptop, net)
    rt.start()
    net.internet_up = False
    rt.tick()
    assert buffer.count() == 3 and rt.held_since is None  # router, main, backup target


def test_a_network_recorded_later_by_setup_is_picked_up(buffer):
    laptop = Laptop()
    unset = AgentConfig(site_name="Home")
    rt = runtime(buffer, laptop, settings=unset)
    rt.start()
    assert rt.where is Where.UNSET
    assert "doesn't know Home's network" in execute({"type": "diagnose"}, rt)[2]
    rt.deps.load_config = at_home
    assert rt.check_network() is Where.HOME


@pytest.fixture
def paired_before_1_0_1(tmp_path, monkeypatch):
    monkeypatch.setenv("KINLAN_HOME", str(tmp_path))
    config.save(AgentConfig(agent_id="a-1", site_id="s-1", site_name="Home"))


def answers(reply):
    return lambda _prompt: reply


def test_setup_asks_once_and_records_the_network_on_yes(paired_before_1_0_1):
    here, said = Network("192.168.1.0/24", "192.168.1.1", ROUTER), []
    assert homenet.confirm(answers("no"), said.append, here) is False
    assert config.load().home_gateway_mac is None
    assert homenet.confirm(answers("yes"), said.append, here) is True
    saved = config.load()
    assert (saved.home_gateway_mac, saved.home_network) == (ROUTER, "192.168.1.0/24")
    asked = []
    assert homenet.confirm(asked.append, said.append, here) is True and asked == []  # once


def test_setup_doesnt_guess_without_a_router(paired_before_1_0_1):
    said = []
    assert homenet.confirm(answers("yes"), said.append, Network(None, None, None)) is False
    assert config.load().home_gateway_mac is None and "will wait" in said[-1]


def test_coming_back_to_the_network_wakes_the_uploader(buffer):
    """Nov 29 outage test: the laptop was off Home's network for 14 min, the uploader's backoff
    grew to 5 min, and the backlog waited 81 s after the laptop was back. Now it's woken."""
    laptop, woken = Laptop(), []
    laptop.go(SCHOOL)
    rt = runtime(buffer, laptop)
    rt.on_reconnect = lambda: woken.append(1)
    rt.start()
    assert woken == []
    laptop.go(INFO)
    assert rt.check_network() is Where.HOME and woken == [1]
    rt.check_network()
    assert woken == [1]  # only on the way back, not at every check
