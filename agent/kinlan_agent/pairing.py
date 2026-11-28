"""``kinlan-agent pair`` and ``kinlan-agent status`` (plan, Section 3.6).

Pairing asks for consent **before** contacting the server, so nothing is linked to a
Circle unless the person agreed to monitor only networks they may monitor.

Pairing records the network the PC is on as the site's network. On a network one of its sites
already uses, pairing replaces that site's pairing; on a new network it adds a site, so a
laptop can monitor home and a lab, each while it's there (#94).
"""

from __future__ import annotations

import platform
import socket
from collections.abc import Callable

import httpx

from kinlan_agent import __version__, config, homenet, tokenstore
from kinlan_agent.buffer import Buffer

CONSENT = (
    "KinLAN will scan this network for devices, measure its latency and check a short list "
    "of risky ports.\nOnly monitor networks you own or are authorized to monitor."
)




def pair(
    api_url: str,
    code: str | None = None,
    *,
    ask: Callable[[str], str] = input,
    say: Callable[[str], None] = print,
    client: httpx.Client | None = None,
    get_netinfo: Callable | None = None,
    resolve: Callable[[str], str | None] = homenet.resolve_mac,
) -> int:
    """Pair this PC with a site. Returns a process exit code."""
    say(CONSENT)
    if ask('Type "yes" to agree: ').strip().lower() != "yes":
        say("Not paired. Nothing was sent.")
        return 1
    code = (code or ask("Pairing code from the app (6 digits): ")).strip().replace(" ", "")
    if not (len(code) == 6 and code.isdigit()):
        say("A pairing code is 6 digits. Make one in the app: Settings > Add a site.")
        return 1
    if get_netinfo is None:
        from kinlan_agent.netinfo import get_netinfo
    # Pairing happens on the network being added, so this is the site's network (homenet.py).
    network = homenet.current(get_netinfo, resolve)
    settings = config.load()
    if settings.paired and settings.home_gateway_mac and not network.gateway_mac:
        say("Can't identify this network's router, so it can't be told apart from the sites")
        say("this PC already monitors. Connect to the network you're adding and try again.")
        return 1
    body = {
        "code": code,
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "agent_version": __version__,
        "network_cidr": network.cidr,
    }
    client = client or httpx.Client(timeout=20)
    try:
        r = client.post(api_url.rstrip("/") + "/api/v1/agent/pair", json=body)
    except httpx.HTTPError as exc:
        say(f"Couldn't reach {api_url} ({exc}). Check the internet connection and try again.")
        return 1
    if not r.is_success:
        try:
            message = r.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            message = f"HTTP {r.status_code}"
        say(f"Pairing failed: {message}")
        return 1
    data = r.json()
    settings = _record(config.load(), data, network, api_url)
    names = [f"{s.site_name} ({s.home_network or 'network not recorded'})"
             for s in config.site_configs(settings)]
    say(f'Paired with "{data["site_name"]}". This PC monitors: ' + "; ".join(names) + ".")
    say("Each site is monitored only while this PC is on its network.")
    return 0


def _record(settings: config.AgentConfig, data: dict, network, api_url: str):
    """Save a new pairing: in place of the site on this network (or of the same site), or as a
    further site when this is a new network."""
    entry = config.SiteEntry(
        agent_id=data["agent_id"],
        site_id=data["site_id"],
        site_name=data["site_name"],
        home_gateway_mac=network.gateway_mac,
        home_network=network.cidr,
    )

    def same(site_id: str | None, mac: str | None, cidr: str | None) -> bool:
        recorded = config.AgentConfig(home_gateway_mac=mac, home_network=cidr)
        return site_id == entry.site_id or homenet.where(recorded, network) is homenet.Where.HOME

    settings.api_url = api_url
    first = not settings.paired or not settings.home_gateway_mac
    if first or same(settings.site_id, settings.home_gateway_mac, settings.home_network):
        for key in config.SITE_FIELDS:
            setattr(settings, key, getattr(entry, key))
        tokenstore.save_token(data["agent_token"])  # agent.token: the first site's
    else:
        index = next(
            (
                i
                for i, s in enumerate(settings.sites)
                if same(s.site_id, s.home_gateway_mac, s.home_network)
            ),
            None,
        )
        if index is None:
            settings.sites.append(entry)
        else:
            old = settings.sites[index]
            if old.site_id != entry.site_id:
                old_site = config.AgentConfig(slot=old.site_id)
                tokenstore.delete_token(config.token_file(old_site))
            settings.sites[index] = entry
        extra = config.AgentConfig(slot=entry.site_id)
        tokenstore.save_token(data["agent_token"], config.token_file(extra))
    config.save(settings)
    return settings


_HERE = {
    homenet.Where.HOME: "monitoring it: this PC is on its network",
    homenet.Where.AWAY: "waiting: this PC is on another network",
    homenet.Where.UNKNOWN: "can't identify this network's router",
    homenet.Where.UNSET: "the agent waits until its network is recorded (run KinLAN-Agent.exe)",
}


def status(say: Callable[[str], None] = print) -> int:
    problem = config.read_error()
    if problem:
        say(problem + "\nFix the file (or delete it and pair again).")
        return 1
    settings = config.load()
    if not settings.paired:
        say("Not paired. Run: kinlan-agent pair")
        return 1
    from kinlan_agent import installer

    task = installer.task_state()
    if task:
        startup = task
    elif tokenstore.is_admin():
        startup = "not installed (kinlan-agent install)"
    else:  # Windows hides SYSTEM tasks from terminals that aren't administrator
        startup = "can't be seen from this terminal; run status as administrator"
    say(f"Server:       {settings.api_url}")
    say(f"At startup:   {startup}")
    network = homenet.current()
    say(f"This PC:      on {network.describe()}")
    healthy = True
    for site in config.site_configs(settings):
        path = config.token_file(site)
        has_token = tokenstore.load_token(path) is not None
        if has_token:
            token_state = "saved"
        elif path.exists() and not tokenstore.is_admin():
            token_state = "saved, readable from an administrator terminal"
        else:
            token_state = "MISSING: pair again"
        with Buffer(config.buffer_file(site)) as buffer:
            waiting, last = buffer.count(), buffer.get_meta("last_upload_at")
        say("")
        say(f"Site:         {site.site_name} ({site.site_id})")
        say(f"Agent:        {site.agent_id} (token {token_state})")
        say(f"Its network:  {homenet.home_description(site)}")
        say(f"Now:          {_HERE[homenet.where(site, network)]}")
        say(f"Last upload:  {last or 'never'}")
        say(f"Waiting:      {waiting} items in the buffer")
        healthy = healthy and (has_token or path.exists())
    return 0 if healthy else 1
