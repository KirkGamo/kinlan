"""One PC, several sites: a laptop that monitors home and a lab, each while it's there (#94)."""

import threading
import time
from types import SimpleNamespace

import httpx
import pytest

from kinlan_agent import config, pairing, tokenstore
from kinlan_agent.buffer import Buffer
from kinlan_agent.config import AgentConfig, SiteEntry
from kinlan_agent.homenet import Where
from kinlan_agent.runner import Runtime, run_sites
from tests.test_homenet import SCHOOL, SCHOOL_ROUTER, Laptop
from tests.test_runner import ROUTER, Net, at_home, deps


@pytest.fixture(autouse=True)
def home_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("KINLAN_HOME", str(tmp_path))
    return tmp_path


HOME_NET = SimpleNamespace(network="192.168.1.0/24", gateway="192.168.1.1")
LAB_NET = SimpleNamespace(network="10.124.36.0/22", gateway="10.124.36.1")
OTHER_NET = SimpleNamespace(network="10.0.0.0/24", gateway="10.0.0.1")
ROUTERS = {"192.168.1.1": ROUTER, "10.124.36.1": SCHOOL_ROUTER, "10.0.0.1": "0a:0b:0c:0d:0e:0f"}


def server(*sites):
    """Answers each pairing with the next site."""
    queue = list(sites)

    def handler(request):
        site_id, name = queue.pop(0)
        return httpx.Response(
            200,
            json={"agent_id": f"agent-{site_id}", "agent_token": f"tok-{site_id}",
                  "site_id": site_id, "site_name": name},
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def pair_on(net, client) -> int:
    return pairing.pair(
        "http://api.test", "123456", ask=lambda _: "yes", say=lambda _: None,
        client=client, get_netinfo=lambda: net, resolve=ROUTERS.get,
    )


def test_pairing_on_a_new_network_adds_a_site_with_its_own_token(home_dir):
    client = server(("home", "Home"), ("lab", "CCS Lab"))
    assert pair_on(HOME_NET, client) == 0
    assert pair_on(LAB_NET, client) == 0
    sites = config.site_configs(config.load())
    assert [(s.site_name, s.home_gateway_mac, s.home_network) for s in sites] == [
        ("Home", ROUTER, "192.168.1.0/24"),
        ("CCS Lab", SCHOOL_ROUTER, "10.124.36.0/22"),
    ]
    assert [tokenstore.load_token(config.token_file(s)) for s in sites] == ["tok-home", "tok-lab"]
    assert config.buffer_file(sites[0]).name == "buffer.db"  # the first site keeps its files
    assert config.buffer_file(sites[1]).name == "buffer-lab.db"


def test_pairing_again_on_a_known_network_replaces_that_site(home_dir):
    client = server(("home", "Home"), ("lab", "CCS Lab"), ("lab2", "CCS Lab 2"), ("home", "Home"))
    for net in (HOME_NET, LAB_NET, LAB_NET, HOME_NET):
        assert pair_on(net, client) == 0
    sites = config.site_configs(config.load())
    assert [s.site_id for s in sites] == ["home", "lab2"]
    assert not (home_dir / "agent-lab.token").exists()  # the replaced pairing's token is gone
    assert tokenstore.load_token(config.token_file(sites[1])) == "tok-lab2"


def test_a_new_site_needs_an_identified_router(home_dir):
    assert pair_on(HOME_NET, server(("home", "Home"))) == 0
    said = []
    unknown = SimpleNamespace(network="10.9.9.0/24", gateway="10.9.9.1")  # ARP gets no answer
    code = pairing.pair(
        "http://api.test", "123456", ask=lambda _: "yes", say=said.append,
        client=server(), get_netinfo=lambda: unknown, resolve=ROUTERS.get,
    )
    assert code == 1 and "Can't identify this network's router" in said[-2]
    assert len(config.site_configs(config.load())) == 1


def test_the_file_keeps_sites_after_the_first_as_tables(home_dir):
    saved = AgentConfig(agent_id="a", site_id="home", site_name="Home", home_gateway_mac=ROUTER,
                        sites=[SiteEntry(agent_id="b", site_id="lab", site_name="CCS Lab",
                                         home_gateway_mac=SCHOOL_ROUTER)])
    text = config.save(saved).read_text(encoding="utf-8")
    assert text.rstrip().endswith('home_gateway_mac = "00:1a:2b:3c:4d:5e"')
    assert "\n[[sites]]\n" in text and "slot" not in text
    assert config.load_site("lab").site_name == "CCS Lab"


def lab_config() -> AgentConfig:
    return AgentConfig(site_name="CCS Lab", site_id="lab", home_gateway_mac=SCHOOL_ROUTER,
                       home_network="10.124.36.0/22", slot="lab")


def runtime_for(settings, laptop, buffer):
    d = deps(Net())
    d.get_netinfo, d.gateway_mac, d.route = laptop.get_netinfo, laptop.gateway_mac, laptop.route
    d.load_config = lambda: settings
    return Runtime(settings, buffer, d)


def test_only_the_site_whose_network_the_pc_is_on_measures():
    laptop = Laptop()
    with Buffer(":memory:") as home_buffer, Buffer(":memory:") as lab_buffer:
        home = runtime_for(at_home(), laptop, home_buffer)
        lab = runtime_for(lab_config(), laptop, lab_buffer)
        for rt in (home, lab):
            rt.start()
            rt.tick()
        assert (home.where, lab.where) == (Where.HOME, Where.AWAY)
        assert (home_buffer.count(), lab_buffer.count()) == (2, 0)

        laptop.go(SCHOOL)  # to the lab
        for rt in (home, lab):
            rt.tick()
        assert (home.where, lab.where) == (Where.AWAY, Where.HOME)
        assert (home_buffer.count(), lab_buffer.count()) == (2, 2)


def test_run_sites_runs_each_site_with_its_own_buffer():
    laptop = Laptop()
    stop = threading.Event()
    with Buffer(":memory:") as home_buffer, Buffer(":memory:") as lab_buffer:
        sites = []
        for settings, buffer in ((at_home(), home_buffer), (lab_config(), lab_buffer)):
            settings.api_url, settings.monitor_interval_s = "http://127.0.0.1:9", 1
            sites.append((settings, "tok", buffer))
        d = deps(Net())
        d.get_netinfo, d.gateway_mac, d.route = laptop.get_netinfo, laptop.gateway_mac, laptop.route
        runner = threading.Thread(target=run_sites, args=(sites, d, stop), daemon=True)
        runner.start()
        deadline = time.monotonic() + 5
        while home_buffer.count() < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        stop.set()
        runner.join(timeout=10)
        assert not runner.is_alive()
        assert home_buffer.count() >= 2 and lab_buffer.count() == 0
