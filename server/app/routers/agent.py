"""The agent API: pairing, ingest, the command long-poll and command results (Sections 1.1,
1.2, 3.6 and 4.3).

Every upload doubles as a heartbeat. A resent batch (same batch_id) is acknowledged but stored
only once, so the agent can retry freely after a dropped connection.
"""

import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query, Request
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import alerts
from app.agent_auth import CurrentAgent, GzipRoute, check_version
from app.agent_schemas import (
    CommandBatch,
    CommandOut,
    CommandResultIn,
    IngestIn,
    IngestOut,
    PairIn,
    PairOut,
)
from app.commands import expire_stale, to_out
from app.deps import DB
from app.device_types import infer_type
from app.errors import ApiError
from app.models import (
    Agent,
    Command,
    CommandStatus,
    DetectedBy,
    Device,
    IngestBatch,
    Outage,
    PairingCode,
    PingSample,
    PingTest,
    PortFinding,
    Site,
    SiteStatus,
)
from app.ratelimit import limiter
from app.schemas import ErrorOut
from app.security import keyed_hash, sha256_hex

FUTURE_TOLERANCE = timedelta(minutes=5)
OFFLINE_AFTER = timedelta(minutes=11)  # two missed 5-minute scans
MAX_WAIT = 25

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    route_class=GzipRoute,
    responses={401: {"model": ErrorOut}, 426: {"model": ErrorOut}},
)


# ---------------------------------------------------------------- pairing


@router.post("/pair", response_model=PairOut, responses={404: {"model": ErrorOut}})
@limiter.limit("10/minute")
def pair(request: Request, body: PairIn, db: DB) -> PairOut:
    """Swap a 6-digit pairing code for this agent's token. Re-pairing a site replaces its agent."""
    check_version(body.agent_version)
    now = datetime.now(UTC)
    code = db.scalar(
        select(PairingCode)
        .where(
            PairingCode.code_hash == keyed_hash(body.code),
            PairingCode.used_at.is_(None),
            PairingCode.expires_at > now,
        )
        .with_for_update()
    )
    if code is None:
        raise ApiError(
            404,
            "pairing_code_invalid",
            "That code is wrong or expired. Make a new one in the app (codes last 10 minutes).",
        )
    code.used_at = now
    site = db.get(Site, code.site_id)
    db.execute(
        update(Agent)
        .where(Agent.site_id == site.id, Agent.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    token = secrets.token_urlsafe(32)  # 32 random bytes, base64url
    agent = Agent(
        site_id=site.id,
        token_hash=sha256_hex(token),
        hostname=body.hostname,
        os=body.os,
        version=body.agent_version,
        last_seen_at=now,
    )
    db.add(agent)
    if body.network_cidr:
        site.cidr = body.network_cidr
    db.commit()
    return PairOut(agent_id=agent.id, agent_token=token, site_id=site.id, site_name=site.name)


# ---------------------------------------------------------------- ingest


def _store_devices(db: DB, site: Site, body: IngestIn, now: datetime) -> tuple[int, list[Device]]:
    """Upsert scanned devices. The site's first scan is its baseline (no alerts, no penalty)."""
    if not body.devices:
        return 0, []
    first_scan = db.scalar(select(Device.id).where(Device.site_id == site.id).limit(1)) is None
    existing = {
        d.mac: d
        for d in db.scalars(
            select(Device).where(
                Device.site_id == site.id, Device.mac.in_([d.mac for d in body.devices])
            )
        )
    }
    gateway = str(body.netinfo.gateway) if body.netinfo and body.netinfo.gateway else None
    new: list[Device] = []
    for item in body.devices:
        ip = str(item.ip) if item.ip else None
        device = existing.get(item.mac)
        if device is None:
            device = Device(
                site_id=site.id,
                mac=item.mac,
                baseline=first_scan,
                device_type=infer_type(item.vendor, item.hostname, is_gateway=ip == gateway),
                first_seen_at=now,
            )
            db.add(device)
            existing[item.mac] = device
            if not first_scan:
                new.append(device)
        device.ip = ip or device.ip
        device.hostname = item.hostname or device.hostname
        device.vendor = item.vendor or device.vendor
        device.last_seen_at, device.online = now, True
    db.flush()
    db.execute(
        update(Device)
        .where(Device.site_id == site.id, Device.last_seen_at < now - OFFLINE_AFTER)
        .values(online=False)
    )
    return len(body.devices), new


def _store_outages(db: DB, site: Site, body: IngestIn) -> tuple[int, list[Outage]]:
    """Outages the agent recorded while it couldn't reach us; matched by start time.
    Also returns the ones that closed in this batch, for the back-online alert."""
    stored, closed = 0, []
    for item in body.outages:
        row = db.scalar(
            select(Outage).where(Outage.site_id == site.id, Outage.started_at == item.started_at)
        )
        if row is None:
            row = Outage(
                site_id=site.id,
                started_at=item.started_at,
                ended_at=item.ended_at,
                cause=item.cause,
                detected_by=DetectedBy.agent,
            )
            db.add(row)
            stored += 1
            if item.ended_at is not None:
                closed.append(row)
        elif row.ended_at is None and item.ended_at is not None:
            row.ended_at, row.cause = item.ended_at, item.cause
            stored += 1
            closed.append(row)
    return stored, closed


def _store_ports(
    db: DB, site: Site, body: IngestIn, now: datetime
) -> tuple[int, list[tuple[Device, int, str]]]:
    """Upsert port findings; returns those that are newly open (first seen, or back after being
    resolved), for the risky-port alert."""
    if not body.port_findings:
        return 0, []
    devices = {
        d.mac: d
        for d in db.scalars(
            select(Device).where(
                Device.site_id == site.id, Device.mac.in_({f.mac for f in body.port_findings})
            )
        )
    }
    known = [f for f in body.port_findings if f.mac in devices]
    if not known:
        return 0, []
    already_open = set(
        db.execute(
            select(PortFinding.device_id, PortFinding.port).where(
                PortFinding.device_id.in_({devices[f.mac].id for f in known}),
                PortFinding.resolved_at.is_(None),
            )
        ).all()
    )
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
    newly_open = [
        (devices[f.mac], f.port, f.service)
        for f in known
        if (devices[f.mac].id, f.port) not in already_open
    ]
    return len(known), newly_open


@router.post("/ingest", response_model=IngestOut, responses={400: {"model": ErrorOut}})
def ingest(body: IngestIn, agent: CurrentAgent, db: DB) -> IngestOut:
    """One batch from the agent's outbox: ping samples, a device scan, closed outages and port
    findings. Also the heartbeat: the site becomes `online` and its last contact is updated."""
    check_version(body.agent_version)
    now = datetime.now(UTC)
    site = db.get(Site, agent.site_id)
    agent.version = body.agent_version

    fresh = db.scalar(
        pg_insert(IngestBatch)
        .values(batch_id=body.batch_id, agent_id=agent.id, received_at=now)
        .on_conflict_do_nothing()
        .returning(IngestBatch.batch_id)
    )
    was_unreachable = site.status == SiteStatus.unreachable
    site.last_seen_at = now
    site.status = SiteStatus.online
    if fresh is None:  # already stored; acknowledge so the agent deletes it from its outbox
        alerts.came_back(db, site, was_unreachable, [], now)
        db.commit()
        return IngestOut(status="duplicate")

    if body.netinfo:
        site.cidr = body.netinfo.cidr or site.cidr
        site.gateway_ip = str(body.netinfo.gateway) if body.netinfo.gateway else site.gateway_ip

    limit = now + FUTURE_TOLERANCE
    accepted = [s for s in body.samples if s.ts <= limit]
    if accepted:
        db.execute(
            insert(PingSample),
            [
                {
                    "site_id": site.id,
                    "target": s.target,
                    "ip": str(s.ip),
                    "ts": s.ts,
                    "rtt_ms": s.rtt_ms if s.ok else None,
                    "ok": s.ok,
                }
                for s in accepted
            ],
        )
    devices, new_devices = _store_devices(db, site, body, now)
    outages, closed = _store_outages(db, site, body)
    ports, newly_open = _store_ports(db, site, body, now)
    db.flush()
    alerts.new_devices(db, site, new_devices, now)
    alerts.risky_ports(db, site, newly_open, now)
    alerts.came_back(db, site, was_unreachable, closed, now)
    if accepted:
        alerts.thresholds(db, site, now)
    db.commit()
    return IngestOut(
        status="stored",
        samples=len(accepted),
        rejected_samples=len(body.samples) - len(accepted),
        devices=devices,
        new_devices=len(new_devices),
        outages=outages,
        port_findings=ports,
    )


# ---------------------------------------------------------------- commands


@router.get("/commands", response_model=CommandBatch)
def poll_commands(
    agent: CurrentAgent,
    db: DB,
    wait: int = Query(20, ge=0, le=MAX_WAIT, description="Seconds to hold the request open"),
) -> CommandBatch:
    """Long-poll: returns as soon as a command is waiting, or an empty list after `wait` s.
    Returned commands are marked `running`."""
    deadline = time.monotonic() + wait
    site_id = agent.site_id
    db.commit()  # save the heartbeat before waiting
    while True:
        expire_stale(db, site_id)
        picked = list(
            db.scalars(
                select(Command)
                .where(Command.site_id == site_id, Command.status == CommandStatus.pending)
                .order_by(Command.created_at)
                .limit(5)
                .with_for_update(skip_locked=True)
            )
        )
        for cmd in picked:
            cmd.status = CommandStatus.running
        db.commit()
        if picked or time.monotonic() >= deadline:
            return CommandBatch(commands=[to_out(c) for c in picked])
        time.sleep(1)


@router.post(
    "/commands/{command_id}/result",
    response_model=CommandOut,
    responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def command_result(
    command_id: uuid.UUID, body: CommandResultIn, agent: CurrentAgent, db: DB
) -> CommandOut:
    """Report how a command went. A ping test result is also kept in the device's history."""
    cmd = db.get(Command, command_id)
    if cmd is None or cmd.site_id != agent.site_id:
        raise ApiError(404, "command_not_found", "No such command for this agent.")
    if cmd.status != CommandStatus.running:
        raise ApiError(409, "command_not_running", f"That command is already {cmd.status.value}.")
    now = datetime.now(UTC)
    cmd.status = CommandStatus.done if body.ok else CommandStatus.failed
    cmd.result = (
        body.result if body.ok else {"error": body.error or "The agent reported a failure."}
    )
    cmd.finished_at = now
    if cmd.type == "ping_test" and body.ok and body.result:
        r = body.result
        db.add(
            PingTest(
                device_id=uuid.UUID(cmd.params["device_id"]),
                ts=now,
                sent=int(r.get("sent", 0)),
                received=int(r.get("received", 0)),
                loss_pct=float(r.get("loss_pct", 0)),
                min_ms=r.get("min_ms"),
                avg_ms=r.get("avg_ms"),
                max_ms=r.get("max_ms"),
                jitter_ms=r.get("jitter_ms"),
            )
        )
    db.commit()
    return to_out(cmd)
