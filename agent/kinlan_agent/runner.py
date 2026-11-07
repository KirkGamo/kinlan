"""``kinlan-agent run``: monitor, scan, upload and answer commands until stopped (plan, 3.1, 3.5).

Four background threads share one SQLite buffer:

* **monitor**: pings the gateway and the internet every 10 s; samples and outages go to the
  outbox, and a diagnose runs automatically when an outage starts;
* **scanner**: a device scan every 5 minutes (plus hourly buffer cleanup);
* **uploader**: sends the outbox every 30 s, draining any backlog oldest first;
* **commands**: long-polls the server and runs scan, ping test and diagnose on request.

Every network operation comes through :class:`CloudDeps`, so tests run it against fakes.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from kinlan_agent import __version__, diagnose, discovery, monitor, netinfo, pingtest
from kinlan_agent.buffer import Buffer
from kinlan_agent.config import AgentConfig
from kinlan_agent.icmp import EchoReply, echo
from kinlan_agent.uploader import Uploader

log = logging.getLogger("kinlan.runner")
PRUNE_EVERY_S = 3600


@dataclass
class CloudDeps:
    get_netinfo: Callable[..., netinfo.NetInfo] = netinfo.get_netinfo
    scan: Callable[[netinfo.NetInfo], discovery.ScanResult] = discovery.scan
    choose_targets: Callable[..., list[str]] = monitor.choose_internet_targets
    run_diagnose: Callable[..., diagnose.Diagnosis] = diagnose.run
    ping_test: Callable[..., pingtest.PingStats] = pingtest.ping_test
    send: Callable[[str, int], EchoReply] = echo


def scan_item(info: netinfo.NetInfo, result: discovery.ScanResult) -> dict:
    return {"netinfo": info.to_dict(), "devices": [d.to_dict() for d in result.devices]}


# ---------------------------------------------------------------- commands


def execute(command: dict, runtime: Runtime) -> tuple[bool, dict | None, str | None]:
    """Run one command; returns (ok, result, error) for POST /agent/commands/{id}/result."""
    kind, params = command.get("type"), command.get("params") or {}
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
            return False, None, "Port checks arrive in a later agent version."
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
        log.info(
            "monitoring %s via gateway %s; internet targets %s",
            self.info.network,
            self.info.gateway,
            ", ".join(self.targets),
        )

    def tick(self) -> None:
        tick, event = self.monitor.tick()
        self.buffer.add_many("sample", [s.to_dict() for s in tick.samples], now=tick.ts)
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
            except Exception:
                log.exception("automatic diagnose failed")
        elif event and event.kind == "ended" and self.open_outage_id is not None:
            self.buffer.close_outage(self.open_outage_id, event.outage.ended_at)
            log.warning("internet back after %.0f s", event.outage.duration_s or 0)
            self.open_outage_id = None

    def scan_now(self) -> tuple[netinfo.NetInfo, discovery.ScanResult]:
        with self._scan_lock:
            info = self.deps.get_netinfo(max_prefix=self.config.max_scan_prefix)
            result = self.deps.scan(info)
            self.buffer.add("scan", scan_item(info, result))
            if self.monitor and info.gateway != self.monitor.gateway:
                log.info("gateway changed to %s", info.gateway)
                self.monitor.gateway = info.gateway
            self.info = info
            return info, result


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
    uploader = Uploader(buffer, config.api_url, token)
    poller = CommandPoller(runtime, config.api_url, token)
    last_prune = [0.0]

    def scan_and_prune() -> None:
        runtime.scan_now()
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
