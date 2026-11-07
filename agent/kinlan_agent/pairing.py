"""``kinlan-agent pair`` and ``kinlan-agent status`` (plan, Section 3.6).

Pairing asks for consent **before** contacting the server, so nothing is linked to a
Circle unless the person agreed to monitor only networks they may monitor.
"""

from __future__ import annotations

import platform
import socket
from collections.abc import Callable

import httpx

from kinlan_agent import __version__, config, tokenstore
from kinlan_agent.buffer import Buffer

CONSENT = (
    "KinLAN will scan this network for devices, measure its latency and check a short list "
    "of risky ports.\nOnly monitor networks you own or are authorized to monitor."
)


def _network_cidr(get_netinfo: Callable) -> str | None:
    try:
        return str(get_netinfo().network)
    except Exception:
        return None


def pair(
    api_url: str,
    code: str | None = None,
    *,
    ask: Callable[[str], str] = input,
    say: Callable[[str], None] = print,
    client: httpx.Client | None = None,
    get_netinfo: Callable | None = None,
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
    body = {
        "code": code,
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "agent_version": __version__,
        "network_cidr": _network_cidr(get_netinfo),
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
    tokenstore.save_token(data["agent_token"])
    settings = config.load()
    settings.api_url, settings.agent_id = api_url, data["agent_id"]
    settings.site_id, settings.site_name = data["site_id"], data["site_name"]
    config.save(settings)
    say(f'Paired with "{data["site_name"]}". Start monitoring with: kinlan-agent run')
    return 0


def status(say: Callable[[str], None] = print) -> int:
    problem = config.read_error()
    if problem:
        say(problem + "\nFix the file (or delete it and pair again).")
        return 1
    settings = config.load()
    if not settings.paired:
        say("Not paired. Run: kinlan-agent pair")
        return 1
    has_token = tokenstore.load_token() is not None
    with Buffer() as buffer:
        waiting, last = buffer.count(), buffer.get_meta("last_upload_at")
    say(f"Site:         {settings.site_name} ({settings.site_id})")
    say(f"Server:       {settings.api_url}")
    token_state = "saved" if has_token else "MISSING: pair again"
    say(f"Agent:        {settings.agent_id} (token {token_state})")
    say(f"Last upload:  {last or 'never'}")
    say(f"Waiting:      {waiting} items in the buffer")
    return 0 if has_token else 1
