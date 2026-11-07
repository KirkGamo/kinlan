"""Sites, the site summary and agent pairing codes (Sections 3.6, 4.3 and 4.6).

Viewers read; admins create sites, rename them and make pairing codes; owners delete a site
and its history.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Response
from sqlalchemy import delete, func, select

from app.authz import require_role, require_site
from app.deps import DB, CurrentUser
from app.errors import ApiError
from app.health import HealthInputs, compute
from app.models import (
    Alert,
    AlertSettings,
    Device,
    Outage,
    PairingCode,
    PingSample,
    PortFinding,
    Role,
    Site,
    Target,
)
from app.schemas import (
    DeductionOut,
    ErrorOut,
    LatestSample,
    PairingCodeOut,
    SiteIn,
    SiteList,
    SiteOut,
    SitePatch,
    SiteSummary,
)
from app.security import keyed_hash, new_pairing_code

PAIRING_TTL = timedelta(minutes=10)

router = APIRouter(
    tags=["sites"],
    responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}, 404: {"model": ErrorOut}},
)


# ---------------------------------------------------------------- sites


@router.get("/circles/{circle_id}/sites", response_model=SiteList)
def list_sites(circle_id: uuid.UUID, user: CurrentUser, db: DB) -> SiteList:
    """Every site in the Circle, oldest first."""
    require_role(db, user, circle_id, Role.viewer)
    sites = db.scalars(select(Site).where(Site.circle_id == circle_id).order_by(Site.created_at))
    return SiteList(items=[SiteOut.model_validate(s) for s in sites])


@router.post("/circles/{circle_id}/sites", status_code=201, response_model=SiteOut)
def create_site(circle_id: uuid.UUID, body: SiteIn, user: CurrentUser, db: DB) -> SiteOut:
    """Add a site (one network). It stays `pending` until an agent pairs with it."""
    require_role(db, user, circle_id, Role.admin)
    site = Site(circle_id=circle_id, name=body.name, timezone=body.timezone)
    db.add(site)
    db.flush()
    db.add(AlertSettings(site_id=site.id))  # the documented defaults
    db.commit()
    return SiteOut.model_validate(site)


@router.get("/sites/{site_id}", response_model=SiteOut)
def get_site(site_id: uuid.UUID, user: CurrentUser, db: DB) -> SiteOut:
    return SiteOut.model_validate(require_site(db, user, site_id, Role.viewer))


@router.patch("/sites/{site_id}", response_model=SiteOut)
def update_site(site_id: uuid.UUID, body: SitePatch, user: CurrentUser, db: DB) -> SiteOut:
    """Rename a site or change its time zone. Admins and owners."""
    site = require_site(db, user, site_id, Role.admin)
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(site, field, value)
    db.commit()
    return SiteOut.model_validate(site)


@router.delete("/sites/{site_id}", status_code=204)
def delete_site(site_id: uuid.UUID, user: CurrentUser, db: DB) -> Response:
    """Delete a site with its devices, history and agent. Owners only, like deleting a Circle."""
    db.delete(require_site(db, user, site_id, Role.owner))
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- summary


def _latest(db: DB, site_id: uuid.UUID, target: Target) -> LatestSample | None:
    row = db.scalars(
        select(PingSample)
        .where(PingSample.site_id == site_id, PingSample.target == target)
        .order_by(PingSample.ts.desc())
        .limit(1)
    ).first()
    return LatestSample(ts=row.ts, rtt_ms=row.rtt_ms, ok=row.ok) if row else None


def health_inputs(db: DB, site_id: uuid.UUID, now: datetime) -> tuple[HealthInputs, int]:
    """The last 24 hours, measured; also returns the needs-review device count."""
    since = now - timedelta(hours=24)
    total, ok, avg_ms = db.execute(
        select(
            func.count(),
            func.count().filter(PingSample.ok),
            func.avg(PingSample.rtt_ms).filter(PingSample.ok),
        ).where(
            PingSample.site_id == site_id,
            PingSample.target == Target.internet,
            PingSample.ts >= since,
        )
    ).one()
    outages = db.scalar(
        select(func.count()).where(Outage.site_id == site_id, Outage.started_at >= since)
    )
    needs_review = db.scalar(
        select(func.count()).where(
            Device.site_id == site_id, Device.baseline.is_(False), Device.trusted.is_(False)
        )
    )
    risky = db.scalar(
        select(func.count())
        .select_from(PortFinding)
        .join(Device, Device.id == PortFinding.device_id)
        .where(Device.site_id == site_id, PortFinding.resolved_at.is_(None))
    )
    inputs = HealthInputs(
        internet_avg_ms=float(avg_ms) if avg_ms is not None else None,
        loss_pct=100.0 * (total - ok) / total if total else None,
        outages=outages,
        new_untrusted_devices=needs_review,
        risky_ports=risky,
    )
    return inputs, needs_review


@router.get("/sites/{site_id}/summary", response_model=SiteSummary)
def site_summary(site_id: uuid.UUID, user: CurrentUser, db: DB) -> SiteSummary:
    """Everything the Overview needs for one site: status, grade with its reasons, the latest
    gateway and internet pings, device counts, open alerts and any outage in progress."""
    site = require_site(db, user, site_id, Role.viewer)
    now = datetime.now(UTC)
    inputs, needs_review = health_inputs(db, site.id, now)
    health = compute(inputs)
    devices_total, devices_online = db.execute(
        select(func.count(), func.count().filter(Device.online)).where(Device.site_id == site.id)
    ).one()
    open_alerts = db.scalar(
        select(func.count()).where(
            Alert.site_id == site.id, Alert.acked_at.is_(None), Alert.resolved_at.is_(None)
        )
    )
    open_outage = db.scalar(
        select(func.min(Outage.started_at)).where(
            Outage.site_id == site.id, Outage.ended_at.is_(None)
        )
    )
    return SiteSummary(
        site_id=site.id,
        status=site.status,
        last_seen_at=site.last_seen_at,
        score=health.score,
        grade=health.grade,
        grade_summary=health.summary,
        deductions=[DeductionOut(**d.to_dict()) for d in health.deductions],
        internet=_latest(db, site.id, Target.internet),
        gateway=_latest(db, site.id, Target.gateway),
        devices_total=devices_total,
        devices_online=devices_online,
        needs_review=needs_review,
        open_alerts=open_alerts,
        open_outage_since=open_outage,
    )


# ---------------------------------------------------------------- pairing


@router.post("/sites/{site_id}/pairing-code", status_code=201, response_model=PairingCodeOut)
def create_pairing_code(site_id: uuid.UUID, user: CurrentUser, db: DB) -> PairingCodeOut:
    """A 6-digit code, valid 10 minutes, that the agent's `pair` command exchanges for its token.
    Making a new code cancels the site's earlier unused ones."""
    site = require_site(db, user, site_id, Role.admin)
    now = datetime.now(UTC)
    db.execute(
        delete(PairingCode).where(PairingCode.site_id == site.id, PairingCode.used_at.is_(None))
    )
    for _ in range(10):  # an active code must be unique across sites, since it's all the agent has
        code = new_pairing_code()
        clash = db.scalar(
            select(PairingCode.id).where(
                PairingCode.code_hash == keyed_hash(code),
                PairingCode.used_at.is_(None),
                PairingCode.expires_at > now,
            )
        )
        if clash is None:
            break
    else:
        raise ApiError(503, "pairing_busy", "Couldn't make a unique code. Try again.")
    row = PairingCode(site_id=site.id, code_hash=keyed_hash(code), expires_at=now + PAIRING_TTL)
    db.add(row)
    db.commit()
    return PairingCodeOut(code=code, expires_at=row.expires_at)
