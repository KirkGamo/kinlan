"""Devices: list, detail, edit and ping-test history (Section 4.3; docs/design/briefs.md, 2).

Any member reads; admins and owners rename, set the type or owner, and mark devices trusted.
Marking a device trusted resolves its open "new device" alert.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Query
from sqlalchemy import case, func, select, tuple_, update

from app import cursors
from app.authz import require_device, require_site
from app.deps import DB, CurrentUser
from app.device_schemas import (
    DeviceDetail,
    DeviceList,
    DeviceOut,
    DeviceOwner,
    DevicePatch,
    PingTestList,
    PingTestOut,
    PortFindingOut,
)
from app.errors import ApiError
from app.models import (
    Agent,
    Alert,
    Device,
    Membership,
    PingTest,
    PortFinding,
    Role,
    Site,
    User,
)
from app.ports import INFO_PORTS, is_risky
from app.schemas import ErrorOut

router = APIRouter(
    tags=["devices"],
    responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}, 404: {"model": ErrorOut}},
)


def display_name(d: Device) -> str:
    return d.custom_name or d.hostname or d.vendor or d.mac


def _risky_counts(db: DB, device_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not device_ids:
        return {}
    rows = db.execute(
        select(PortFinding.device_id, func.count())
        .where(
            PortFinding.device_id.in_(device_ids),
            PortFinding.resolved_at.is_(None),
            PortFinding.port.not_in(INFO_PORTS),  # web admin pages are information, not risk
        )
        .group_by(PortFinding.device_id)
    ).all()
    return dict(rows)


def _short(name: str | None) -> str | None:
    """`LAPTOP-01.lan` and `laptop-01` are the same machine: compare the bare, lowercased name."""
    return name.split(".")[0].strip().lower() or None if name else None


def _agent_names(db: DB, site_id: uuid.UUID) -> set[str]:
    """Hostnames of the site's active agents, as each reported when it paired."""
    names = db.scalars(
        select(Agent.hostname).where(Agent.site_id == site_id, Agent.revoked_at.is_(None))
    )
    return {n for n in (_short(h) for h in names) if n}


def _out(d: Device, owner: User | None, risky: int, agents: set[str] = frozenset()) -> dict:
    return {
        "id": d.id,
        "site_id": d.site_id,
        "display_name": display_name(d),
        "custom_name": d.custom_name,
        "hostname": d.hostname,
        "vendor": d.vendor,
        "mac": d.mac,
        "ip": str(d.ip) if d.ip is not None else None,
        "device_type": d.device_type,
        "owner": DeviceOwner(user_id=owner.id, display_name=owner.display_name) if owner else None,
        "trusted": d.trusted,
        "baseline": d.baseline,
        "needs_review": not d.baseline and not d.trusted,
        "online": d.online,
        "first_seen_at": d.first_seen_at,
        "last_seen_at": d.last_seen_at,
        "open_risky_ports": risky,
        "is_agent": _short(d.hostname) in agents,
    }


@router.get("/sites/{site_id}/devices", response_model=DeviceList)
def list_devices(
    site_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    status: Literal["all", "online", "offline", "review"] = "all",
    owner: Literal["any", "me", "shared"] = "any",
) -> DeviceList:
    """Devices on a site: needs-review first, then online, then offline; by name within each."""
    site = require_site(db, user, site_id, Role.viewer)
    query = (
        select(Device, User)
        .outerjoin(User, User.id == Device.owner_user_id)
        .where(Device.site_id == site.id)
    )
    review = (Device.baseline.is_(False)) & (Device.trusted.is_(False))
    if status == "online":
        query = query.where(Device.online.is_(True))
    elif status == "offline":
        query = query.where(Device.online.is_(False))
    elif status == "review":
        query = query.where(review)
    if owner == "me":
        query = query.where(Device.owner_user_id == user.id)
    elif owner == "shared":
        query = query.where(Device.owner_user_id.is_(None))
    name = func.lower(func.coalesce(Device.custom_name, Device.hostname, Device.vendor, Device.mac))
    query = query.order_by(case((review, 0), else_=1), Device.online.desc(), name)
    rows = db.execute(query).all()
    risky = _risky_counts(db, [d.id for d, _ in rows])
    agents = _agent_names(db, site.id)
    return DeviceList(items=[DeviceOut(**_out(d, u, risky.get(d.id, 0), agents)) for d, u in rows])


def _detail(db: DB, d: Device) -> DeviceDetail:
    owner = db.get(User, d.owner_user_id) if d.owner_user_id else None
    ports = list(
        db.scalars(
            select(PortFinding)
            .where(PortFinding.device_id == d.id, PortFinding.resolved_at.is_(None))
            .order_by(PortFinding.port)
        )
    )
    last = db.scalars(
        select(PingTest).where(PingTest.device_id == d.id).order_by(PingTest.ts.desc()).limit(1)
    ).first()
    return DeviceDetail(
        **_out(d, owner, sum(is_risky(p.port) for p in ports), _agent_names(db, d.site_id)),
        risky_ports=[
            PortFindingOut(
                port=p.port,
                service=p.service,
                info=not is_risky(p.port),
                first_seen_at=p.first_seen_at,
                last_seen_at=p.last_seen_at,
            )
            for p in ports
        ],
        last_ping_test=PingTestOut.model_validate(last, from_attributes=True) if last else None,
    )


@router.get("/devices/{device_id}", response_model=DeviceDetail)
def get_device(device_id: uuid.UUID, user: CurrentUser, db: DB) -> DeviceDetail:
    """One device with its open risky ports and its latest ping test."""
    return _detail(db, require_device(db, user, device_id, Role.viewer))


@router.patch(
    "/devices/{device_id}", response_model=DeviceDetail, responses={400: {"model": ErrorOut}}
)
def update_device(
    device_id: uuid.UUID, body: DevicePatch, user: CurrentUser, db: DB
) -> DeviceDetail:
    """Rename, set the type or owner, or mark trusted. Admins and owners."""
    device = require_device(db, user, device_id, Role.admin)
    sent = body.model_fields_set
    if "custom_name" in sent:
        device.custom_name = body.custom_name or None  # an empty name clears it
    if "device_type" in sent and body.device_type is not None:
        device.device_type = body.device_type
    if "owner_user_id" in sent:
        if body.owner_user_id is not None:
            site = db.get(Site, device.site_id)
            if db.get(Membership, (site.circle_id, body.owner_user_id)) is None:
                raise ApiError(
                    400, "owner_not_member", "A device can only belong to someone in this Circle."
                )
        device.owner_user_id = body.owner_user_id
    if "trusted" in sent and body.trusted is not None:
        device.trusted = body.trusted
        if body.trusted:  # the person reviewed it: its "someone new joined" alert is done
            db.execute(
                update(Alert)
                .where(
                    Alert.site_id == device.site_id,
                    Alert.type == "new_device",
                    Alert.subject_ref == str(device.id),
                    Alert.resolved_at.is_(None),
                )
                .values(resolved_at=datetime.now(UTC))
            )
    db.commit()
    return _detail(db, device)




@router.get("/devices/{device_id}/ping-tests", response_model=PingTestList)
def ping_tests(
    device_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = None,
) -> PingTestList:
    """The device's ping tests, newest first."""
    device = require_device(db, user, device_id, Role.viewer)
    query = select(PingTest).where(PingTest.device_id == device.id)
    if cursor:
        query = query.where(tuple_(PingTest.ts, PingTest.id) < tuple_(*cursors.decode(cursor)))
    rows = list(db.scalars(query.order_by(PingTest.ts.desc(), PingTest.id.desc()).limit(limit + 1)))
    more = len(rows) > limit
    rows = rows[:limit]
    return PingTestList(
        items=[PingTestOut.model_validate(t, from_attributes=True) for t in rows],
        next_cursor=cursors.encode(rows[-1].ts, rows[-1].id) if more and rows else None,
    )
