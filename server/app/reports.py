"""The PDF network report (plan, Section 4.7; required course Features 4 and 5).

One site over 24 hours, 7 days or 30 days:

1. Header: Circle, site, range and when it was made, in the site's time zone.
2. Network: address range, router, and the internet and router figures for the range.
3. Connection chart: internet (yellow, solid) and router (grey, dashed), outages shaded, the
   same look as the app's chart.
4. Ping results: router and internet always, plus every device ping-tested in the range.
5. Outage log.
6. Health grade (last 24 hours) with every deduction.
7. Security recommendations: one per problem found, then the router advice that always applies.
8. Devices.

ReportLab draws the PDF and Matplotlib the chart, both in Manrope (OFL, bundled in
``report_assets``). Pure functions of the gathered data, so the layout is easy to test.
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.health import HealthScore, compute
from app.models import Circle, Device, PingTest, PortFinding, Site
from app.routers.metrics import LatencyOut, latency_data
from app.routers.sites import health_inputs

ASSETS = Path(__file__).with_name("report_assets")
# Matplotlib's font cache lives next to the app, so the Render build makes it once (render.yaml)
# and the running server never pays the ~5 s font scan. Set before matplotlib is imported.
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).parent.parent / ".mplcache"))
SPANS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}
SPAN_WORDS = {"24h": "the last 24 hours", "7d": "the last 7 days", "30d": "the last 30 days"}

# The app's tokens (mobile/src/theme/colors.ts), on paper instead of Night Ground.
INK = "#0B0B0C"
MUTED = "#5E5E66"
RULE = "#D9D9DE"
PANEL = "#F4F4F6"
YELLOW = "#FFD60A"
GREEN = "#1E8E3E"  # status green darkened for white paper (the app's #30D158 is too light to read)
ORANGE = "#B25E00"
RED = "#D92D20"

PORT_ADVICE = {  # the device sheet's advice (device-sheet.tsx)
    21: "FTP sends passwords unencrypted. Turn it off on this device, or use SFTP instead.",
    23: "Telnet sends passwords unencrypted. Turn it off on this device.",
    445: "File sharing (SMB) is open. Keep it off unless you share folders on purpose.",
    3389: "Remote Desktop is open. Turn it off if nobody connects to this PC remotely.",
    5900: "Screen sharing (VNC) is open. Turn it off if you don't use it.",
}
FACTOR_ADVICE = {
    "latency": "Restart the router. If replies stay slow, run a diagnose in the app and share the "
    "result with your internet provider.",
    "loss": "Check the router's cables and move it away from walls and appliances. If pings still "
    "go missing, ask your internet provider to check the line.",
    "outages": "Keep this report's outage log: the start times and causes help when you report the "
    "problem to your internet provider.",
    "devices": "Open Devices in the app, say whose each new device is, and mark the ones you know "
    "as trusted. If one belongs to nobody, change the Wi-Fi password.",
    "ports": "See the open ports below and turn off the services nobody uses.",
}
ROUTER_ADVICE = [
    ("Change the router's admin password", "Use a long one that isn't the Wi-Fi password, and "
     "never the default printed on the router."),
    ("Use WPA3, or WPA2 with AES", "Avoid WEP, WPA and TKIP: they can be broken in minutes."),
    ("Turn off WPS", "The 8-digit PIN can be guessed, which gives away the Wi-Fi password."),
    ("Turn off UPnP unless you need it", "It lets any device on the network open ports to the "
     "internet without asking."),
    ("Keep the router's firewall on and its firmware up to date", "Most routers check for "
     "updates in their admin page; turn on automatic updates if it offers them."),
]
CAUSE_WORDS = {"isp": "Internet provider", "lan": "Inside the network", "unknown": "Unknown"}


# ---------------------------------------------------------------- data


@dataclass
class PingRow:
    name: str
    tests: int | None  # None for the continuous router and internet monitors
    avg_ms: float | None
    max_ms: float | None
    loss_pct: float | None


@dataclass
class ReportData:
    circle: str
    site: str
    zone: ZoneInfo
    span: str
    start: datetime
    end: datetime
    cidr: str | None
    gateway: str | None
    latency: LatencyOut
    pings: list[PingRow]
    devices: list[Device]
    findings: list[tuple[Device, PortFinding]]
    health: HealthScore
    devices_online: int = 0
    notes: list[str] = field(default_factory=list)


def zone_of(site: Site) -> ZoneInfo:
    try:
        return ZoneInfo(site.timezone or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def gather(db: Session, site: Site, span: str, now: datetime | None = None) -> ReportData:
    """Everything the report shows, read once."""
    now = now or datetime.now(UTC)
    start = now - SPANS[span]
    latency = latency_data(db, site.id, span, "both", now)

    pings = []
    for name, key in (("Router", "gateway"), ("Internet", "internet")):
        s = latency.summary.get(key)
        pings.append(PingRow(name, None, s.avg_ms if s else None, s.max_ms if s else None,
                             s.loss_pct if s else None))
    tested = db.execute(
        select(
            Device,
            func.count(PingTest.id),
            func.avg(PingTest.avg_ms),
            func.max(PingTest.max_ms),
            func.avg(PingTest.loss_pct),
        )
        .join(PingTest, PingTest.device_id == Device.id)
        .where(Device.site_id == site.id, PingTest.ts >= start)
        .group_by(Device.id)
        .order_by(func.count(PingTest.id).desc())
    ).all()
    for device, count, avg_ms, max_ms, loss in tested:
        pings.append(PingRow(display_name(device), count, _f(avg_ms), _f(max_ms), _f(loss)))

    devices = list(
        db.scalars(
            select(Device)
            .where(Device.site_id == site.id)
            .order_by(Device.online.desc(), Device.last_seen_at.desc())
        )
    )
    findings = list(
        db.execute(
            select(Device, PortFinding)
            .join(PortFinding, PortFinding.device_id == Device.id)
            .where(Device.site_id == site.id, PortFinding.resolved_at.is_(None))
            .order_by(PortFinding.port)
        ).all()
    )
    inputs, _ = health_inputs(db, site.id, now)
    circle = db.get(Circle, site.circle_id)
    return ReportData(
        circle=circle.name if circle else "",
        site=site.name,
        zone=zone_of(site),
        span=span,
        start=start,
        end=now,
        cidr=site.cidr,
        gateway=site.gateway_ip,
        latency=latency,
        pings=pings,
        devices=devices,
        findings=findings,
        health=compute(inputs),
        devices_online=sum(1 for d in devices if d.online),
    )


def display_name(d: Device) -> str:
    return d.custom_name or d.hostname or d.vendor or d.mac


def _f(v) -> float | None:
    return float(v) if v is not None else None


# ---------------------------------------------------------------- words and numbers


def ms(v: float | None) -> str:
    """Latency the app's way: no decimals from 10 ms, one below."""
    if v is None:
        return "—"
    return f"{v:.0f} ms" if v >= 10 else f"{v:.1f} ms"


def pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f}%" if v < 10 else f"{v:.0f}%"


def when(t: datetime, zone: ZoneInfo, date: bool = True) -> str:
    local = t.astimezone(zone)
    clock = f"{local.hour}:{local.minute:02d}"
    return f"{local:%b} {local.day}, {clock}" if date else clock


def duration(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {secs:02d} s" if secs else f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if minutes else f"{hours} h"


def recommendations(data: ReportData) -> list[tuple[str, str]]:
    """Problems first (most points lost first), then the advice that always applies."""
    out = [
        (d.reason, f"{d.detail} {FACTOR_ADVICE.get(d.factor, '')}".strip())
        for d in sorted(data.health.deductions, key=lambda d: -d.points)
    ]
    for device, finding in data.findings:
        advice = PORT_ADVICE.get(
            finding.port, f"{finding.service} is open. Turn it off if you don't use it."
        )
        out.append((f"Port {finding.port} ({finding.service}) is open on {display_name(device)}",
                    advice))
    return out + ROUTER_ADVICE


# ---------------------------------------------------------------- chart


@cache
def _matplotlib():
    """Matplotlib, loaded and set up once per process (Agg, Manrope, quiet about weights)."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager, patheffects
    from matplotlib import pyplot as plt

    for ttf in sorted(ASSETS.glob("Manrope_*.ttf")):
        font_manager.fontManager.addfont(str(ttf))
    # Manrope ships 500, 700 and 800 here; "normal" (400) quietly falls back to 500.
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
    plt.rcParams.update({"font.family": "Manrope", "font.weight": "medium", "font.size": 8})
    return plt, patheffects


@cache
def _reportlab_fonts() -> None:
    """Manrope for ReportLab, registered once per process; <b> maps to Manrope Bold."""
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    faces = (
        ("Manrope", "Manrope_500Medium.ttf"),
        ("Manrope-Bold", "Manrope_700Bold.ttf"),
        ("Manrope-ExtraBold", "Manrope_800ExtraBold.ttf"),
    )
    for name, file in faces:
        pdfmetrics.registerFont(TTFont(name, str(ASSETS / file)))
    addMapping("Manrope", 0, 0, "Manrope")
    addMapping("Manrope", 1, 0, "Manrope-Bold")
    addMapping("Manrope", 0, 1, "Manrope")
    addMapping("Manrope", 1, 1, "Manrope-Bold")


def warm_up() -> None:
    """Load everything a report needs, so the first report after a deploy or restart is as quick
    as the rest. Run at build time (it fills the font cache) and in the background at startup."""
    plt, _ = _matplotlib()
    fig, ax = plt.subplots(figsize=(1, 1), dpi=50)
    ax.plot([0, 1], [0, 1])
    fig.savefig(io.BytesIO(), format="png")
    plt.close(fig)
    _reportlab_fonts()
    import reportlab.platypus  # noqa: F401  (the layout engine, the slowest import)


def chart_png(data: ReportData) -> bytes:
    """The connection chart as a PNG, drawn like the app's."""
    plt, patheffects = _matplotlib()

    fig, ax = plt.subplots(figsize=(7.0, 2.4), dpi=200)
    zone = data.zone
    least = (data.end - data.start) / 150  # like the app: a short outage stays visible
    for o in data.latency.outages:
        end = max(o.ended_at or data.end, o.started_at + least)
        ax.axvspan(o.started_at.astimezone(zone), end.astimezone(zone), color=RED, alpha=0.16, lw=0)
    gateway = data.latency.series.get("gateway", [])
    internet = data.latency.series.get("internet", [])
    if gateway:
        ax.plot([p.t.astimezone(zone) for p in gateway], [p.avg_ms for p in gateway],
                color=MUTED, lw=1.4, ls=(0, (4, 3)), label="Router")
    if internet:
        ax.plot([p.t.astimezone(zone) for p in internet], [p.avg_ms for p in internet],
                color=YELLOW, lw=2.2, label="Internet",
                path_effects=[patheffects.withStroke(linewidth=3.2, foreground=INK, alpha=0.55)])
    if not gateway and not internet:
        ax.text(0.5, 0.5, "No measurements in this range", transform=ax.transAxes,
                ha="center", va="center", color=MUTED)
    ax.set_xlim(data.start.astimezone(zone), data.end.astimezone(zone))
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Round trip (ms)", color=MUTED)
    ax.grid(axis="y", color=RULE, lw=0.6)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(colors=MUTED, length=0)
    import matplotlib.dates as mdates

    fmt = "%H:%M" if data.span == "24h" else "%b %d"
    ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt, tz=zone))
    if internet or gateway:
        ax.legend(loc="upper left", frameon=False, ncol=2)
    fig.tight_layout()
    out = io.BytesIO()
    fig.savefig(out, format="png")
    plt.close(fig)
    return out.getvalue()


# ---------------------------------------------------------------- PDF


def render(data: ReportData) -> bytes:
    """The report as PDF bytes (A4)."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image,
        KeepTogether,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    _reportlab_fonts()

    def style(name, **kw) -> ParagraphStyle:
        base = {"fontName": "Manrope", "fontSize": 9.5, "leading": 13.5, "textColor": INK,
                "alignment": TA_LEFT}
        return ParagraphStyle(name, **{**base, **kw})

    body = style("body")
    small = style("small", fontSize=8, leading=11, textColor=MUTED)
    label = style("label", fontName="Manrope-ExtraBold", fontSize=7.5, leading=10,
                  textColor=MUTED)
    h1 = style("h1", fontName="Manrope-ExtraBold", fontSize=20, leading=24)
    h2 = style("h2", fontName="Manrope-ExtraBold", fontSize=12.5, leading=16, spaceBefore=12,
               spaceAfter=5, keepWithNext=1)
    strong = style("strong", fontName="Manrope-Bold")
    cell = style("cell", fontSize=8.5, leading=11)
    cell_b = style("cellb", fontName="Manrope-Bold", fontSize=8.5, leading=11)

    def esc(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def table(rows, widths, header=True, zebra=True) -> Table:
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        cmds = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor(RULE)),
        ]
        if header:
            cmds.append(("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(INK)))
        if zebra:
            for i in range(1 if header else 0, len(rows), 2):
                cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor(PANEL)))
        t.setStyle(TableStyle(cmds))
        return t

    def head(*names: str) -> list:
        return [Paragraph(n.upper(), label) for n in names]

    zone = data.zone
    story = []
    # 1. Header
    story.append(Paragraph(f'kin<font name="Manrope-ExtraBold" color="{ORANGE}">LAN</font> '
                           f'<font size="9" color="{MUTED}">Network report</font>', h1))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>{esc(data.site)}</b> · {esc(data.circle)}", strong))
    story.append(Paragraph(
        f"{SPAN_WORDS[data.span].capitalize()}: {when(data.start, zone)} to {when(data.end, zone)} "
        f"({zone.key}). Made {when(data.end, zone)}.", small))

    # 2. Network
    inet = data.latency.summary.get("internet")
    gw = data.latency.summary.get("gateway")
    story.append(Paragraph("Network", h2))
    facts = [
        ["Address range", data.cidr or "—", "Router", data.gateway or "—"],
        ["Internet, average", ms(inet.avg_ms if inet else None), "Internet, lost pings",
         pct(inet.loss_pct if inet else None)],
        ["Router, average", ms(gw.avg_ms if gw else None), "Devices",
         f"{data.devices_online} online of {len(data.devices)}"],
    ]
    fact_rows = [
        [Paragraph(esc(str(c)), cell_b if i % 2 else small) for i, c in enumerate(r)] for r in facts
    ]
    story.append(table(fact_rows, [32 * mm, 50 * mm, 34 * mm, 54 * mm], header=False))

    # 3. Chart
    story.append(Paragraph("Connection", h2))
    story.append(Image(io.BytesIO(chart_png(data)), width=170 * mm, height=170 * mm * 2.4 / 7.0))
    story.append(Paragraph("Average round trip to the internet (solid) and to the router "
                           "(dashed). Red bands are outages.", small))

    # 4. Ping results
    story.append(Paragraph("Ping results", h2))
    rows = [head("Target", "Tests", "Average", "Max", "Lost")]
    for p in data.pings:
        rows.append([Paragraph(esc(p.name), cell_b), Paragraph("Every 10 s" if p.tests is None
                     else str(p.tests), cell), Paragraph(ms(p.avg_ms), cell),
                     Paragraph(ms(p.max_ms), cell), Paragraph(pct(p.loss_pct), cell)])
    story.append(table(rows, [62 * mm, 26 * mm, 27 * mm, 27 * mm, 28 * mm]))
    if len(data.pings) == 2:
        story.append(Paragraph("No device was ping-tested in this range; run a ping test from a "
                               "device in the app to add it here.", small))

    # 5. Outages
    story.append(Paragraph("Outages", h2))
    if data.latency.outages:
        rows = [head("Started", "Ended", "Lasted", "Cause")]
        for o in data.latency.outages:
            rows.append([Paragraph(when(o.started_at, zone), cell),
                         Paragraph("Still down" if o.ongoing else when(o.ended_at, zone), cell),
                         Paragraph(duration(o.duration_s or 0), cell),
                         Paragraph(CAUSE_WORDS.get(o.cause.value, "Unknown"), cell)])
        story.append(table(rows, [44 * mm, 44 * mm, 34 * mm, 48 * mm]))
    else:
        story.append(Paragraph("No outages in this range.", body))

    # 6. Health
    hs = data.health
    grade_color = GREEN if hs.score >= 80 else ORANGE if hs.score >= 60 else RED
    story.append(Paragraph("Health grade (last 24 hours)", h2))
    grade = style("grade", leading=30, spaceAfter=6)
    story.append(Paragraph(f'<font name="Manrope-ExtraBold" size="24" color="{grade_color}">'
                           f'{hs.grade}</font>&nbsp;&nbsp;<font size="11">{hs.score} / 100</font>'
                           f'&nbsp;&nbsp;<font color="{MUTED}">{esc(hs.summary)}</font>', grade))
    if hs.deductions:
        rows = [head("Why", "Points")]
        for d in hs.deductions:
            rows.append([Paragraph(f"<b>{esc(d.reason)}</b><br/>{esc(d.detail)}", cell),
                         Paragraph(f"−{d.points}", cell_b)])
        story.append(table(rows, [150 * mm, 20 * mm]))

    # 7. Security recommendations
    recs = recommendations(data)
    found = len(recs) - len(ROUTER_ADVICE)
    rec_text = style("rec", leftIndent=11, textColor=MUTED, fontSize=8.5, leading=12, spaceAfter=4)
    items = []
    for i, (title, text) in enumerate(recs, 1):
        mark = f'<font color="{RED if i <= found else MUTED}">{i}.</font>'
        items.append(
            [Paragraph(f"{mark} <b>{esc(title)}</b>", body), Paragraph(esc(text), rec_text)]
        )
    # The heading travels with the first recommendation, so it's never left alone at a page end.
    lead = [Paragraph("Security recommendations", h2)]
    if not found:
        lead.append(Paragraph("KinLAN found no problems to fix. These router settings keep it "
                              "that way:", small))
    story.append(KeepTogether(lead + items[0]))
    story.extend(KeepTogether(item) for item in items[1:])

    # 8. Devices
    story.append(Paragraph(f"Devices ({len(data.devices)})", h2))
    rows = [head("Name", "IP address", "Hardware address", "Maker", "Trusted", "Last seen")]
    for d in data.devices:
        ip = str(d.ip) if d.ip else "—"
        rows.append([Paragraph(esc(display_name(d)), cell_b), Paragraph(esc(ip), cell),
                     Paragraph(esc(d.mac), cell), Paragraph(esc(d.vendor or "—"), cell),
                     Paragraph("Yes" if d.trusted else "No", cell),
                     Paragraph("Online" if d.online else when(d.last_seen_at, zone), cell)])
    story.append(table(rows, [32 * mm, 23 * mm, 35 * mm, 32 * mm, 19 * mm, 29 * mm]))

    def footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Manrope", 7.5)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(20 * mm, 12 * mm, f"KinLAN · {data.site} · {when(data.end, zone)}")
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Page {doc.page}")
        canvas.restoreState()

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm,
                            title=f"KinLAN report: {data.site}", author="KinLAN")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()



if __name__ == "__main__":  # python -m app.reports: warm the caches (the Render build runs this)
    warm_up()
