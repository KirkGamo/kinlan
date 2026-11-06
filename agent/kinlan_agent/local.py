"""``kinlan-agent run --local``: everything the agent measures, in the terminal, with no cloud.

Shows, in order: this PC's network, the devices on it, a full diagnose, and then a live
monitor (gateway and internet latency, packet loss, outages and the health grade) that
refreshes every tick until Ctrl+C or ``--ticks`` runs out.

Every network operation is passed in through :class:`LocalDeps`, so tests can run the
whole view against fake data.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from kinlan_agent import diagnose, discovery, health, monitor, netinfo
from kinlan_agent.icmp import EchoReply, echo

STATUS_STYLE = {"pass": "green", "fail": "bold red", "skipped": "dim"}
GRADE_STYLE = {"A": "bold green", "B": "green", "C": "yellow", "D": "bold yellow", "F": "bold red"}


@dataclass
class LocalDeps:
    """The operations ``run_local`` uses; tests swap them for fakes."""

    get_netinfo: Callable[[], netinfo.NetInfo] = netinfo.get_netinfo
    scan: Callable[[netinfo.NetInfo], discovery.ScanResult] = discovery.scan
    choose_targets: Callable[[], list[str]] = monitor.choose_internet_targets
    run_diagnose: Callable[..., diagnose.Diagnosis] = diagnose.run
    send: Callable[[str, int], EchoReply] = echo
    sleep: Callable[[float], None] = time.sleep


@dataclass
class TargetStats:
    """Running statistics for one monitored target during this session."""

    sent: int = 0
    received: int = 0
    total_ms: float = 0.0
    last_ms: float | None = None

    def add(self, sample: monitor.Sample) -> None:
        self.sent += 1
        if sample.ok and sample.rtt_ms is not None:
            self.received += 1
            self.total_ms += sample.rtt_ms
            self.last_ms = sample.rtt_ms
        else:
            self.last_ms = None

    @property
    def avg_ms(self) -> float | None:
        return self.total_ms / self.received if self.received else None

    @property
    def loss_pct(self) -> float | None:
        return 100 * (self.sent - self.received) / self.sent if self.sent else None


@dataclass
class Session:
    """Everything observed since ``run --local`` started."""

    gateway: TargetStats = field(default_factory=TargetStats)
    internet: TargetStats = field(default_factory=TargetStats)
    ticks: int = 0
    outages: list[monitor.Outage] = field(default_factory=list)
    open_outage: monitor.Outage | None = None

    def record(self, tick: monitor.Tick, event: monitor.OutageEvent | None) -> None:
        self.ticks += 1
        for sample in tick.samples:
            if sample.target == "gateway":
                self.gateway.add(sample)
        # One internet result per tick: the main target, or the confirming one if asked.
        internet = [s for s in tick.samples if s.target == "internet"]
        if internet:
            self.internet.add(next((s for s in internet if s.ok), internet[-1]))
        if event and event.kind == "started":
            self.open_outage = event.outage
            self.outages.append(event.outage)
        elif event and event.kind == "ended":
            self.open_outage = None

    def health(self) -> health.HealthScore:
        return health.compute(health.HealthInputs(
            internet_avg_ms=self.internet.avg_ms,
            loss_pct=self.internet.loss_pct,
            outages=len(self.outages),
        ))


def _ms(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f} ms"


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}%"


def network_table(info: netinfo.NetInfo, targets: list[str]) -> Table:
    table = Table(title="This PC's network", show_header=False, title_justify="left")
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Adapter", f"{info.interface_name} ({info.interface_mac or 'no MAC'})")
    table.add_row("Address", f"{info.local_ip} on {info.network}")
    table.add_row("Router (gateway)", info.gateway or "none found")
    table.add_row("DNS servers", ", ".join(info.dns_servers) or "none found")
    table.add_row("Internet targets", ", ".join(targets))
    return table


def devices_table(result: discovery.ScanResult) -> Table:
    title = (f"Devices on {result.network}: {len(result.devices)} found in "
             f"{result.duration_ms / 1000:.1f} s ({result.method} ARP)")
    table = Table(title=title, title_justify="left")
    for column in ("IP address", "MAC address", "Manufacturer", "Name", ""):
        table.add_column(column)
    for d in result.devices:
        role = "router" if d.is_gateway else "this PC" if d.is_self else ""
        table.add_row(d.ip, d.mac, d.vendor or "Unknown", d.hostname or "-", role)
    return table


def diagnose_table(result: diagnose.Diagnosis) -> Table:
    style = "green" if result.healthy else "bold red"
    table = Table(title=f"Diagnose: [{style}]{result.summary}[/]", title_justify="left")
    for column in ("#", "Check", "Result", "Time", "What it means", "Details"):
        table.add_column(column)
    for s in result.steps:
        table.add_row(str(s.n), s.name, f"[{STATUS_STYLE[s.status]}]{s.status}[/]",
                      _ms(s.ms), s.summary, s.detail)
    return table


def monitor_panel(session: Session, gateway: str | None, primary: str) -> Panel:
    table = Table(show_header=True, expand=False)
    for column in ("Target", "Last", "Average", "Loss", "Replies"):
        table.add_column(column)
    rows = []
    if gateway:
        rows.append((f"Router {gateway}", session.gateway))
    rows.append((f"Internet {primary}", session.internet))
    for label, stats in rows:
        table.add_row(label, _ms(stats.last_ms), _ms(stats.avg_ms), _pct(stats.loss_pct),
                      f"{stats.received}/{stats.sent}")
    score = session.health()
    status = ("[bold red]Internet DOWN since "
              f"{session.open_outage.started_at:%H:%M:%S} UTC ({session.open_outage.cause})[/]"
              if session.open_outage else "[green]Internet up[/]")
    lines = [
        table,
        f"{status}   Outages this session: {len(session.outages)}",
        f"Health: [{GRADE_STYLE[score.grade]}]{score.grade} ({score.score}/100)[/]  "
        f"{score.summary}",
    ]
    return Panel(Group(*lines), title=f"Live monitor, tick {session.ticks}",
                 subtitle="Ctrl+C to stop", title_align="left")


def run_local(
    ticks: int | None = None,
    interval_s: float = 10.0,
    console: Console | None = None,
    deps: LocalDeps | None = None,
) -> Session:
    """Run the local view. ``ticks=None`` monitors until Ctrl+C."""
    deps = deps or LocalDeps()
    if console is None:
        # A legacy Windows console can't print every character; never crash on one.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(errors="replace")
        console = Console()

    console.rule("[bold]KinLAN Agent: local mode[/] (not connected to the cloud)")
    with console.status("Reading this PC's network..."):
        info = deps.get_netinfo()
        targets = deps.choose_targets()
    console.print(network_table(info, targets))

    with console.status("Scanning for devices (about 7-15 s)..."):
        scan = deps.scan(info)
    console.print(devices_table(scan))
    for error in scan.errors:
        console.print(f"[yellow]Note:[/] {error}")

    with console.status("Running the six-step diagnose..."):
        result = deps.run_diagnose(internet_targets=tuple(targets[:2]))
    console.print(diagnose_table(result))

    mon = monitor.Monitor(info.gateway, targets, send=deps.send)
    session = Session()
    try:
        with Live(monitor_panel(session, info.gateway, mon.primary), console=console,
                  refresh_per_second=4, transient=False) as live:
            while ticks is None or session.ticks < ticks:
                tick, event = mon.tick()
                session.record(tick, event)
                live.update(monitor_panel(session, info.gateway, mon.primary))
                if ticks is None or session.ticks < ticks:
                    deps.sleep(interval_s)
    except KeyboardInterrupt:
        console.print("Stopped.")
    return session
