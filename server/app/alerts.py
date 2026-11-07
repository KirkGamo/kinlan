"""The alert engine (plan, Section 4.4).

Rules run during ingest and in the 1-minute heartbeat job:

| Alert        | Trigger (default; per-site settings)               | Severity          |
|--------------|----------------------------------------------------|-------------------|
| new_device   | a MAC never seen on the site, after the baseline   | warning           |
| unreachable  | no contact from the agent for over 120 s           | critical          |
| back_online  | first upload after unreachable, or outage closed   | info              |
| high_latency | internet average over 150 ms in the last 5 min     | warning           |
| packet_loss  | loss over 5 % in the last 5 min                    | warning           |
| risky_port   | a risky port found open on a device                | critical for FTP/Telnet |

Duplicate suppression: an alert of the same type for the same site and subject doesn't fire
again within 30 minutes while it's still open. Copy follows docs/design/brand.md (voice).
Push delivery to phones arrives with Expo push in Sprint 3; :func:`notify` is its hook.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import (
    Alert,
    AlertSettings,
    DetectedBy,
    Device,
    Outage,
    OutageCause,
    PingSample,
    Site,
    SiteStatus,
    Target,
)

log = logging.getLogger("kinlan.alerts")

SUPPRESS_FOR = timedelta(minutes=30)
WINDOW = timedelta(minutes=5)
MIN_SAMPLES = 6  # one minute of 10-second pings, so one lost ping can't raise an alert
RISKY_CRITICAL = {21, 23}  # FTP and Telnet send passwords unencrypted
CAUSE_WORDS = {"isp": "internet provider outage", "lan": "problem inside the network"}


def notify(alert: Alert) -> None:
    """Hook for push delivery (Expo, Sprint 3). For now the alert is stored and logged."""
    log.info("alert %s for site %s: %s", alert.type, alert.site_id, alert.title)


def raise_alert(
    db: Session,
    site: Site,
    type_: str,
    severity: str,
    title: str,
    body: str,
    subject_ref: str | None = None,
    now: datetime | None = None,
) -> Alert | None:
    """Create an alert unless the same one is already open and recent."""
    now = now or datetime.now(UTC)
    duplicate = db.scalar(
        select(Alert.id).where(
            Alert.site_id == site.id,
            Alert.type == type_,
            Alert.subject_ref.is_(None)
            if subject_ref is None
            else Alert.subject_ref == subject_ref,
            Alert.resolved_at.is_(None),
            Alert.created_at > now - SUPPRESS_FOR,
        )
    )
    if duplicate:
        return None
    alert = Alert(
        site_id=site.id,
        type=type_,
        severity=severity,
        title=title,
        body=body,
        subject_ref=subject_ref,
        created_at=now,
    )
    db.add(alert)
    db.flush()
    notify(alert)
    return alert


def resolve(db: Session, site: Site, type_: str, now: datetime | None = None) -> int:
    """Mark the site's open alerts of a type as resolved (the condition cleared)."""
    return db.execute(
        update(Alert)
        .where(Alert.site_id == site.id, Alert.type == type_, Alert.resolved_at.is_(None))
        .values(resolved_at=now or datetime.now(UTC))
    ).rowcount


def settings_for(db: Session, site: Site) -> AlertSettings:
    settings = db.get(AlertSettings, site.id)
    if settings is None:  # sites made before alert settings existed
        settings = AlertSettings(site_id=site.id)
        db.add(settings)
        db.flush()
    return settings


def device_name(device: Device) -> str:
    return device.custom_name or device.hostname or device.vendor or device.mac


def duration_words(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {secs:02d} s" if secs else f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if minutes else f"{hours} h"


# ---------------------------------------------------------------- rules


def new_devices(db: Session, site: Site, devices: list[Device], now: datetime) -> None:
    if not devices or not settings_for(db, site).notify_new_device:
        return
    for device in devices:
        name = device_name(device)
        detail = " · ".join(str(x) for x in (device.vendor, device.ip) if x)
        raise_alert(
            db,
            site,
            "new_device",
            "warning",
            f"Someone new joined: {name}",
            f"{detail}. Whose is it? Mark it as trusted if you know it.",
            subject_ref=str(device.id),
            now=now,
        )


def risky_ports(
    db: Session, site: Site, found: list[tuple[Device, int, str]], now: datetime
) -> None:
    for device, port, service in found:
        raise_alert(
            db,
            site,
            "risky_port",
            "critical" if port in RISKY_CRITICAL else "warning",
            f"{service.upper()} is open on {device_name(device)}",
            f"Port {port} ({service}) answered on {device.ip or device.mac}. "
            "Turn this service off on the device unless you need it.",
            subject_ref=f"{device.id}:{port}",
            now=now,
        )


def went_unreachable(db: Session, site: Site, now: datetime) -> None:
    """Called by the heartbeat job when the agent has been silent too long."""
    site.status = SiteStatus.unreachable
    since = site.last_seen_at or now
    db.add(
        Outage(
            site_id=site.id,
            started_at=since,
            cause=OutageCause.unknown,
            detected_by=DetectedBy.server,
        )
    )
    raise_alert(
        db,
        site,
        "unreachable",
        "critical",
        f"{site.name} is unreachable",
        f"The agent hasn't reported since {since:%H:%M} UTC. Possible internet or power outage.",
        now=now,
    )


def came_back(
    db: Session, site: Site, was_unreachable: bool, closed: list[Outage], now: datetime
) -> None:
    """After the agent reconnects (or reports an outage it measured), say it's back."""
    if not was_unreachable and not closed:
        return
    if was_unreachable:
        db.execute(
            update(Outage)
            .where(
                Outage.site_id == site.id,
                Outage.ended_at.is_(None),
                Outage.detected_by == DetectedBy.server,
            )
            .values(ended_at=now)
        )
        resolve(db, site, "unreachable", now)
    # Prefer the agent's own measurement: it knows the exact start, end and cause.
    measured = max(closed, key=lambda o: o.ended_at) if closed else None
    if measured is not None:
        seconds = (measured.ended_at - measured.started_at).total_seconds()
        cause = CAUSE_WORDS.get(OutageCause(measured.cause).value, "cause unknown")
        title = f"{site.name} is back online after {duration_words(seconds)}"
        body = f"The internet was down from {measured.started_at:%H:%M} UTC ({cause})."
        ref = f"outage:{measured.started_at.isoformat()}"
    else:
        title, body, ref = f"{site.name} is back online", "The agent is reporting again.", None
    raise_alert(db, site, "back_online", "info", title, body, subject_ref=ref, now=now)


def thresholds(db: Session, site: Site, now: datetime) -> None:
    """High latency and packet loss over the last 5 minutes; resolves when they clear."""
    settings = settings_for(db, site)
    total, ok, avg_ms = db.execute(
        select(
            func.count(),
            func.count().filter(PingSample.ok),
            func.avg(PingSample.rtt_ms).filter(PingSample.ok),
        ).where(
            PingSample.site_id == site.id,
            PingSample.target == Target.internet,
            PingSample.ts > now - WINDOW,
        )
    ).one()
    if total < MIN_SAMPLES:
        return
    loss = 100.0 * (total - ok) / total
    if avg_ms is not None and avg_ms > settings.latency_ms:
        raise_alert(
            db,
            site,
            "high_latency",
            "warning",
            "The internet is slow to respond",
            f"Average {avg_ms:.0f} ms over the last 5 minutes (alert above "
            f"{settings.latency_ms:.0f} ms).",
            now=now,
        )
    elif avg_ms is not None:
        resolve(db, site, "high_latency", now)
    if loss > settings.loss_pct:
        raise_alert(
            db,
            site,
            "packet_loss",
            "warning",
            "Data is getting lost on the way to the internet",
            f"{loss:.0f}% of pings got no reply in the last 5 minutes (alert above "
            f"{settings.loss_pct:.0f}%).",
            now=now,
        )
    else:
        resolve(db, site, "packet_loss", now)
