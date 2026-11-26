"""``kinlan-agent run``: monitor, scan, upload and answer commands until stopped (plan, 3.1, 3.5).

Background threads share one SQLite buffer:

* **monitor**: pings the gateway and the internet every 10 s; samples and outages go to the
  outbox, and a diagnose runs automatically when an outage starts;
* **scanner**: a device scan every 5 minutes (plus hourly buffer cleanup);
* **uploader**: sends the outbox every 30 s, draining any backlog oldest first;
* **commands**: long-polls the server and runs scan, ping test and diagnose on request;
* **network**: every minute, checks that this PC is still on its site's network
  (homenet.py). Elsewhere the agent stays quiet: no samples, scans or commands.

Every network operation comes through :class:`CloudDeps`, so tests run it against fakes.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx

from kinlan_agent import (
    __version__,
    config,
    diagnose,
    discovery,
    homenet,
    monitor,
    netinfo,
    pingtest,
    portcheck,
)
from kinlan_agent.buffer import Buffer
from kinlan_agent.config import AgentConfig
from kinlan_agent.homenet import Where
from kinlan_agent.icmp import EchoReply, echo
from kinlan_agent.uploader import Uploader

log = logging.getLogger("kinlan.runner")
PRUNE_EVERY_S = 3600
RECHECK_TARGETS_EVERY_S = 3600  # some networks block a resolver for a while (plan 3.2)
CHECK_NETWORK_EVERY_S = 60
# Failures while the router can't be identified are held this long: a laptop changing
# networks reconnects within it, while a dead router at home outlasts it.
HOLD_DOUBTFUL_S = 120


@dataclass
class CloudDeps:
    get_netinfo: Callable[..., netinfo.NetInfo] = netinfo.get_netinfo
    scan: Callable[[netinfo.NetInfo], discovery.ScanResult] = discovery.scan
    choose_targets: Callable[..., list[str]] = monitor.choose_internet_targets
    run_diagnose: Callable[..., diagnose.Diagnosis] = diagnose.run
    ping_test: Callable[..., pingtest.PingStats] = pingtest.ping_test
    port_check: Callable[..., portcheck.PortCheck] = portcheck.check
    send: Callable[[str, int], EchoReply] = echo
    gateway_mac: Callable[[str], str | None] = homenet.resolve_mac
    load_config: Callable[[], AgentConfig] = config.load  # setup may record the network later
    route: Callable[[], tuple[str | None, str | None]] = netinfo.route_now


def scan_item(info: netinfo.NetInfo, result: discovery.ScanResult) -> dict:
    return {"netinfo": info.to_dict(), "devices": [d.to_dict() for d in result.devices]}


# ---------------------------------------------------------------- commands


def execute(command: dict, runtime: Runtime) -> tuple[bool, dict | None, str | None]:
    """Run one command; returns (ok, result, error) for POST /agent/commands/{id}/result."""
    kind, params = command.get("type"), command.get("params") or {}
    if kind in ("scan", "ping_test", "diagnose", "port_check") and not runtime.active:
        return False, None, runtime.not_here()
    try:
        if kind == "scan":
            started = time.monotonic()
            info, result = runtime.scan_now()
            return (
                True,
                {
                    "devices": [d.to_dict() for d in result.devices],
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "network": result.network,
                },
                None,
            )
        if kind == "ping_test":
            ip = params.get("ip")
            if not ip:
                return False, None, "The server didn't say which address to ping."
            stats = runtime.deps.ping_test(
                ip, count=int(params.get("count", 10)), send=runtime.deps.send
            )
            return True, stats.to_dict(), None
        if kind == "diagnose":
            targets = tuple(runtime.targets[:2]) if len(runtime.targets) >= 2 else None
            result = (
                runtime.deps.run_diagnose(internet_targets=targets)
                if targets
                else runtime.deps.run_diagnose()
            )
            return True, result.to_dict(), None
        if kind == "port_check":
            # The server names the targets (one device, or the whole site); older servers don't,
            # so then every device from the latest scan is checked.
            given = [portcheck.Target(t["mac"], t["ip"]) for t in params.get("targets") or []]
            result = runtime.port_check_now(given or None)
            return True, result.to_dict(), None
        return False, None, f"This agent doesn't know the command {kind!r}."
    except Exception as exc:  # report, never crash the poller
        log.exception("command %s failed", kind)
        return False, None, f"{type(exc).__name__}: {exc}"


class CommandPoller:
    def __init__(
        self,
        runtime: Runtime,
        api_url: str,
        token: str,
        client: httpx.Client | None = None,
        wait_s: int = 20,
    ):
        self.runtime = runtime
        self.base = api_url.rstrip("/") + "/api/v1/agent/commands"
        self.headers = {"Authorization": f"Bearer {token}"}
        self.client = client or httpx.Client(timeout=wait_s + 15)
        self.wait_s = wait_s

    def poll_once(self) -> bool | None:
        """One long-poll. True: ran commands; False: none waiting; None: failed."""
        try:
            r = self.client.get(self.base, params={"wait": self.wait_s}, headers=self.headers)
        except httpx.HTTPError as exc:
            log.info("command poll failed: %s", exc)
            return None
        if r.status_code in (401, 426):
            raise PermissionError(r.text)
        if not r.is_success:
            return None
        commands = r.json().get("commands", [])
        for cmd in commands:
            ok, result, error = execute(cmd, self.runtime)
            body = {"ok": ok, "result": result, "error": error}
            try:
                self.client.post(f"{self.base}/{cmd['id']}/result", json=body, headers=self.headers)
            except httpx.HTTPError as exc:
                log.warning("couldn't report result of %s: %s", cmd.get("type"), exc)
        return bool(commands)

    def run(self, stop: threading.Event) -> None:
        delay = 5.0
        while not stop.is_set():
            try:
                outcome = self.poll_once()
            except PermissionError:
                log.error("server refused this agent's command polling; stopping it")
                return
            if outcome is None:
                stop.wait(delay)
                delay = min(60.0, delay * 2)
            else:
                delay = 5.0


# ---------------------------------------------------------------- runtime


@dataclass
class Runtime:
    config: AgentConfig
    buffer: Buffer
    deps: CloudDeps = field(default_factory=CloudDeps)
    info: netinfo.NetInfo | None = None
    targets: list[str] = field(default_factory=list)
    monitor: monitor.Monitor | None = None
    open_outage_id: int | None = None
    last_devices: list[portcheck.Target] = field(default_factory=list)
    where: Where = Where.UNKNOWN  # until the first check_network()
    network: homenet.Network | None = None
    route: tuple[str | None, str | None] | None = None  # (local IP, gateway) at the last check
    held: list[tuple[str, dict, datetime]] = field(default_factory=list)
    held_since: datetime | None = None
    _scan_lock: threading.Lock = field(default_factory=threading.Lock)

    def start(self) -> None:
        """Read the network, pick internet targets and resume an outage left open."""
        self.info = self.deps.get_netinfo(max_prefix=self.config.max_scan_prefix)
        self.targets = self.deps.choose_targets(self.config.internet_targets, send=self.deps.send)
        self.monitor = monitor.Monitor(self.info.gateway, self.targets, send=self.deps.send)
        still_open = self.buffer.current_outage()
        if still_open:  # the PC restarted mid-outage: keep the true start time
            self.monitor.detector.current = monitor.Outage(still_open.started_at, still_open.cause)
            self.open_outage_id = still_open.id
        log.info("internet targets %s", ", ".join(self.targets))
        self.check_network()

    # --- which network ------------------------------------------------------------------

    @property
    def active(self) -> bool:
        """True while this PC is on its site's network, so measuring it is measuring the site."""
        return self.where is Where.HOME

    def _site(self) -> str:
        return self.config.site_name or "this site"

    def not_here(self) -> str:
        if self.where is Where.UNSET:
            return (
                f"This agent doesn't know {self._site()}'s network yet. Run KinLAN-Agent.exe once "
                "on the PC while it's on that network."
            )
        now_on = (self.network.cidr if self.network else None) or "another network"
        return f"The agent's PC isn't on {self._site()}'s network right now (it's on {now_on})."

    def check_network(self) -> Where:
        """Find out whether this PC is on its site's network; start or pause monitoring."""
        try:
            info = self.deps.get_netinfo(max_prefix=self.config.max_scan_prefix)
        except Exception:
            info = None
        net = homenet.identify(info, self.deps.gateway_mac)
        self.route = (info.local_ip, info.gateway) if info else (None, None)
        try:
            saved = self.deps.load_config()
        except Exception:
            saved = self.config
        if saved.home_gateway_mac and not self.config.home_gateway_mac:
            self.config.home_gateway_mac = saved.home_gateway_mac
            self.config.home_network = saved.home_network
        state = homenet.where(self.config, net)
        if state is Where.UNKNOWN:
            state = self.where  # router off or no network: keep the last answer
        was, self.where, self.network = self.where, state, net
        if state is was:
            return state
        if state is Where.HOME:
            if info is not None and self.monitor is not None:
                self.info, self.monitor.gateway = info, info.gateway
            log.info("on %s's network, %s: monitoring it", self._site(), net.describe())
        elif state is Where.UNSET:
            log.warning("%s", self.not_here())
        else:
            log.warning(
                "%s %s's is %s. Waiting.",
                self.not_here(),
                self._site(),
                homenet.home_description(self.config),
            )
        if was is Where.HOME:
            self._forget_open_outage()
        return state

    def _forget_open_outage(self) -> None:
        """Leaving the site's network looks like an outage from inside (the router stops
        answering); it was the PC that left, so the outage isn't kept."""
        if self.monitor is not None:
            self.monitor.detector = monitor.OutageDetector()
        if self.open_outage_id is not None:
            self.buffer.drop_outage(self.open_outage_id)
            self.open_outage_id = None
        if self.held:
            log.info("dropped %d measurements taken while leaving the network", len(self.held))
        self.held, self.held_since = [], None

    # --- measurements that might not be the site's -------------------------------------

    def _route_changed(self) -> bool:
        try:
            return self.deps.route() != self.route
        except Exception:
            return False

    def _router_seen(self) -> bool:
        """True if the site's router answered the last network check."""
        net = self.network
        return bool(net and net.gateway_mac) and homenet.where(self.config, net) is Where.HOME

    def _queue(self, kind: str, payload: dict, ts: datetime) -> None:
        if self.held_since is not None:
            self.held.append((kind, payload, ts))
        else:
            self.buffer.add(kind, payload, now=ts)

    def _release(self) -> None:
        for kind, payload, ts in self.held:
            self.buffer.add(kind, payload, now=ts)
        self.held, self.held_since = [], None

    def _sort_out(self, tick: monitor.Tick) -> bool:
        """Before queueing a tick: a failing ping while the router can't be identified may be
        this PC leaving the network rather than the network failing, so hold its measurements
        until that's clear. Returns False if the PC has left (drop the tick)."""
        if tick.gateway_ok is not False and tick.internet_ok:
            self._release()
            return True
        self.check_network()
        if not self.active:
            return False
        if self._router_seen():
            self._release()  # the router answers: a real problem, e.g. the provider
        elif self.held_since is None:
            self.held_since = tick.ts
            log.info("router not identified; holding measurements until it's clear why")
        elif (tick.ts - self.held_since).total_seconds() > HOLD_DOUBTFUL_S:
            log.info("still no router after %d s: sending what was held", HOLD_DOUBTFUL_S)
            self._release()
        return True

    # --- measuring ----------------------------------------------------------------------

    def tick(self) -> None:
        if not self.active:
            return
        if self._route_changed():
            # A new route can mean another network whose 192.168.1.1 also answers (seen Nov 26:
            # 192 ms through a phone hotspot), so find out before measuring anything.
            self.check_network()
            if not self.active:
                return
        tick, event = self.monitor.tick()
        if not self._sort_out(tick):
            return
        for sample in tick.samples:
            self._queue("sample", sample.to_dict(), tick.ts)
        if event and event.kind == "started":
            self.open_outage_id = self.buffer.open_outage(
                event.outage.started_at, event.outage.cause
            )
            log.warning(
                "internet down since %s (%s); running diagnose",
                event.outage.started_at,
                event.outage.cause,
            )
            try:
                result = self.deps.run_diagnose(internet_targets=tuple(self.targets[:2]))
                log.warning("diagnose: %s", result.summary)
                # Kept for the app's diagnose history; it uploads once the internet is back.
                now = datetime.now(UTC)
                finished = now.isoformat().replace("+00:00", "Z")
                self._queue("diagnose", {"finished_at": finished, "result": result.to_dict()}, now)
            except Exception:
                log.exception("automatic diagnose failed")
        elif event and event.kind == "ended" and self.open_outage_id is not None:
            self.buffer.close_outage(self.open_outage_id, event.outage.ended_at)
            log.warning("internet back after %.0f s", event.outage.duration_s or 0)
            self.open_outage_id = None

    def recheck_targets(self) -> bool:
        """Pick the internet targets again (not mid-outage, when none would answer).
        Returns True if they changed."""
        if self.monitor is None or self.monitor.detector.current is not None:
            return False
        chosen = self.deps.choose_targets(self.config.internet_targets, send=self.deps.send)
        if chosen[:2] == self.targets[:2]:
            return False
        log.info("internet targets now %s (were %s)", ", ".join(chosen), ", ".join(self.targets))
        self.targets = chosen
        self.monitor.primary, self.monitor.confirm = chosen[0], chosen[1]
        return True

    def scan_now(self) -> tuple[netinfo.NetInfo, discovery.ScanResult]:
        with self._scan_lock:
            info = self.deps.get_netinfo(max_prefix=self.config.max_scan_prefix)
            result = self.deps.scan(info)
            self.buffer.add("scan", scan_item(info, result))
            if self.monitor and info.gateway != self.monitor.gateway:
                log.info("gateway changed to %s", info.gateway)
                self.monitor.gateway = info.gateway
            self.info = info
            self.last_devices = [portcheck.Target(d.mac, d.ip) for d in result.devices]
            return info, result

    def port_check_now(self, targets: list[portcheck.Target] | None = None) -> portcheck.PortCheck:
        """Check risky ports on `targets`, or on every device from the latest scan."""
        if targets is None:
            if not self.last_devices:
                self.scan_now()
            targets = self.last_devices
        skip = self.info.local_ip if self.info else None
        result = self.deps.port_check(targets, skip_ip=skip)
        log.info(
            "port check: %d devices, %d open ports, %d ms",
            len(result.macs), len(result.open), result.duration_ms,
        )
        return result

    def daily_port_check(self) -> None:
        """The scheduled check; its result goes out through the outbox like everything else."""
        if not self.active:
            log.info("port check skipped: %s", self.not_here())
            return
        self.buffer.add("port_check", self.port_check_now().to_dict())


def seconds_until(at: str, now: datetime | None = None) -> float:
    """Seconds from now until the next local time `at` ("03:00"); 03:00 if `at` is malformed."""
    now = now or datetime.now().astimezone()
    try:
        hour, minute = (int(x) for x in at.split(":"))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except ValueError:
        target = now.replace(hour=3, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _daily(stop: threading.Event, at: str, work: Callable[[], None], name: str) -> None:
    while not stop.wait(seconds_until(at)):
        try:
            work()
        except Exception:
            log.exception("%s failed; trying again tomorrow", name)


def _loop(stop: threading.Event, every_s: float, work: Callable[[], None], name: str) -> None:
    while not stop.is_set():
        started = time.monotonic()
        try:
            work()
        except Exception:
            log.exception("%s failed; continuing", name)
        stop.wait(max(0.0, every_s - (time.monotonic() - started)))


def run(
    config: AgentConfig,
    token: str,
    buffer: Buffer | None = None,
    deps: CloudDeps | None = None,
    stop: threading.Event | None = None,
) -> None:
    """Run until Ctrl+C (or ``stop`` is set)."""
    buffer = buffer or Buffer()
    stop = stop or threading.Event()
    runtime = Runtime(config, buffer, deps or CloudDeps())
    runtime.start()
    uploader = Uploader(buffer, config.api_url, token, scan_interval_s=config.scan_interval_s)
    poller = CommandPoller(runtime, config.api_url, token)
    last_prune = [0.0]
    last_targets = [time.monotonic()]

    def scan_and_prune() -> None:
        if runtime.active:
            runtime.scan_now()
        if time.monotonic() - last_targets[0] > RECHECK_TARGETS_EVERY_S:
            last_targets[0] = time.monotonic()
            runtime.recheck_targets()
        if time.monotonic() - last_prune[0] > PRUNE_EVERY_S:
            removed = buffer.prune()
            last_prune[0] = time.monotonic()
            if removed:
                log.warning("buffer full or old: dropped %d items", removed)

    threads = [
        threading.Thread(
            target=_loop,
            name="monitor",
            daemon=True,
            args=(stop, config.monitor_interval_s, runtime.tick, "monitor"),
        ),
        threading.Thread(
            target=_loop,
            name="scanner",
            daemon=True,
            args=(stop, config.scan_interval_s, scan_and_prune, "scan"),
        ),
        threading.Thread(
            target=uploader.run, name="uploader", daemon=True, args=(stop, config.upload_interval_s)
        ),
        threading.Thread(target=poller.run, name="commands", daemon=True, args=(stop,)),
        threading.Thread(
            target=_loop,
            name="network",
            daemon=True,
            args=(stop, CHECK_NETWORK_EVERY_S, runtime.check_network, "network check"),
        ),
        threading.Thread(
            target=_daily,
            name="ports",
            daemon=True,
            args=(stop, config.port_check_time, runtime.daily_port_check, "port check"),
        ),
    ]
    for t in threads:
        t.start()
    log.info("KinLAN Agent %s running for site %s", __version__, config.site_name or config.site_id)
    try:
        while not stop.is_set():
            stop.wait(1)
            if uploader.stopped_reason:
                log.error("stopping: %s", uploader.stopped_reason)
                stop.set()
    except KeyboardInterrupt:
        stop.set()
    for t in threads:
        t.join(timeout=5)
    log.info("stopped at %s", datetime.now(UTC).isoformat())
