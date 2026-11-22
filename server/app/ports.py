"""Port findings from the agent's port check (plan, Sections 3.2 and 4.4; Feature 5).

A check says which devices and ports were tried and which answered. Answering ports become (or
stay) open findings; a port that was tried and no longer answers is resolved, and so is its
alert. Web admin pages (80, 8080) are kept as information: shown on the device, but they raise
no alert and cost no health points, since every router has one.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Alert, Device, PortFinding, Site

INFO_PORTS = frozenset({80, 8080})


def is_risky(port: int) -> bool:
    return port not in INFO_PORTS


@dataclass(frozen=True)
class Open:
    mac: str
    port: int
    service: str


def apply(
    db: Session,
    site: Site,
    found: Iterable[Open],
    now: datetime,
    checked: dict[str, set[int]] | None = None,
) -> tuple[int, list[tuple[Device, int, str]]]:
    """Record a check. `checked` maps each tried MAC to the ports tried on it (None: an older
    agent that only reports what it found, so nothing is resolved). Returns how many findings
    were stored and the risky ports that are newly open, for the alert."""
    found = list(found)
    macs = {f.mac for f in found} | set(checked or {})
    if not macs:
        return 0, []
    devices = {
        d.mac: d
        for d in db.scalars(select(Device).where(Device.site_id == site.id, Device.mac.in_(macs)))
    }
    known = [f for f in found if f.mac in devices]
    already_open = set(
        db.execute(
            select(PortFinding.device_id, PortFinding.port).where(
                PortFinding.device_id.in_({d.id for d in devices.values()}),
                PortFinding.resolved_at.is_(None),
            )
        ).all()
    )
    if known:
        stmt = pg_insert(PortFinding).values(
            [
                {
                    "id": uuid.uuid4(),
                    "device_id": devices[f.mac].id,
                    "port": f.port,
                    "service": f.service,
                    "first_seen_at": now,
                    "last_seen_at": now,
                }
                for f in known
            ]
        )
        db.execute(
            stmt.on_conflict_do_update(
                constraint="uq_port_findings_device_id_port",
                set_={"last_seen_at": now, "resolved_at": None, "service": stmt.excluded.service},
            )
        )
    open_now = {(devices[f.mac].id, f.port) for f in known}
    for mac, ports in (checked or {}).items():
        device = devices.get(mac)
        if device is None:
            continue
        closed = [
            p for p in ports if (device.id, p) not in open_now and (device.id, p) in already_open
        ]
        if not closed:
            continue
        db.execute(
            update(PortFinding)
            .where(
                PortFinding.device_id == device.id,
                PortFinding.port.in_(closed),
                PortFinding.resolved_at.is_(None),
            )
            .values(resolved_at=now)
        )
        db.execute(
            update(Alert)
            .where(
                Alert.site_id == site.id,
                Alert.type == "risky_port",
                Alert.subject_ref.in_([f"{device.id}:{p}" for p in closed]),
                Alert.resolved_at.is_(None),
            )
            .values(resolved_at=now)
        )
    newly_open = [
        (devices[f.mac], f.port, f.service)
        for f in known
        if (devices[f.mac].id, f.port) not in already_open and is_risky(f.port)
    ]
    return len(known), newly_open
