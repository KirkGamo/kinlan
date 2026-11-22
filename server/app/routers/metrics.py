"""Latency history for charts and the outage log (Section 4.3, Metrics).

Each range is cut into buckets so a chart gets roughly 60-170 points per line:

| range | bucket | source                                                        |
|-------|--------|---------------------------------------------------------------|
| 1h    | 1 min  | raw samples                                                   |
| 24h   | 15 min | raw samples                                                   |
| 7d    | 1 h    | raw samples (kept 7 days)                                     |
| 30d   | 6 h    | hourly rollups, plus raw samples for hours not rolled up yet  |

Buckets carry sums (not averages of averages), so merging rollups with raw samples is exact.
Buckets with no samples are left out: a gap means the agent wasn't reporting.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import and_, exists, func, select, text, tuple_
from sqlalchemy.orm import aliased

from app import cursors
from app.authz import require_site
from app.deps import DB, CurrentUser
from app.models import DetectedBy, Outage, OutageCause, PingHourly, Role
from app.schemas import ErrorOut

router = APIRouter(
    tags=["metrics"],
    responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}, 404: {"model": ErrorOut}},
)

Range = Literal["1h", "24h", "7d", "30d"]
TargetChoice = Literal["internet", "gateway", "both"]
RANGES: dict[str, tuple[timedelta, timedelta]] = {  # span, bucket
    "1h": (timedelta(hours=1), timedelta(minutes=1)),
    "24h": (timedelta(hours=24), timedelta(minutes=15)),
    "7d": (timedelta(days=7), timedelta(hours=1)),
    "30d": (timedelta(days=30), timedelta(hours=6)),
}
ORIGIN = datetime(2000, 1, 1, tzinfo=UTC)  # buckets align to this instant (UTC midnight)


# ---------------------------------------------------------------- response bodies


class Point(BaseModel):
    t: datetime  # bucket start
    avg_ms: float | None  # null when every ping in the bucket was lost
    max_ms: float | None
    loss_pct: float
    samples: int


class Summary(BaseModel):
    avg_ms: float | None
    max_ms: float | None
    loss_pct: float | None
    samples: int


class OutageOut(BaseModel):
    id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    duration_s: float | None
    ongoing: bool
    cause: OutageCause
    detected_by: DetectedBy


class LatencyOut(BaseModel):
    range: Range
    bucket_seconds: int
    since: datetime
    until: datetime
    series: dict[str, list[Point]]
    summary: dict[str, Summary]
    outages: list[OutageOut]


class OutageList(BaseModel):
    items: list[OutageOut]
    next_cursor: str | None = None


# ---------------------------------------------------------------- buckets


@dataclass
class Bucket:
    sum_ms: float = 0.0  # sum of round-trip times of answered pings
    ok: float = 0.0  # answered pings
    total: float = 0.0  # all pings
    max_ms: float | None = None

    def add(self, sum_ms, ok, total, max_ms) -> None:
        self.sum_ms += float(sum_ms or 0)
        self.ok += float(ok or 0)
        self.total += float(total or 0)
        if max_ms is not None:
            self.max_ms = max(self.max_ms or 0.0, float(max_ms))

    def point(self, t: datetime) -> Point:
        return Point(
            t=t,
            avg_ms=round(self.sum_ms / self.ok, 2) if self.ok else None,
            max_ms=round(self.max_ms, 2) if self.max_ms is not None else None,
            loss_pct=round(100.0 * (self.total - self.ok) / self.total, 2) if self.total else 0.0,
            samples=int(round(self.total)),
        )


_RAW = text(
    """
    SELECT date_bin(:step, ts, :origin) AS bucket, target::text AS target,
           sum(rtt_ms) FILTER (WHERE ok) AS sum_ms, count(*) FILTER (WHERE ok) AS ok,
           count(*) AS total, max(rtt_ms) FILTER (WHERE ok) AS max_ms
    FROM ping_samples
    WHERE site_id = :site AND ts >= :since AND ts < :until
    GROUP BY 1, 2
    """
)

_HOURLY = text(
    """
    SELECT date_bin(:step, hour, :origin) AS bucket, target::text AS target,
           sum(avg_ms * samples * (1 - loss_pct / 100.0)) AS sum_ms,
           sum(samples * (1 - loss_pct / 100.0)) AS ok,
           sum(samples) AS total, max(max_ms) AS max_ms
    FROM ping_hourly
    WHERE site_id = :site AND hour >= :since AND hour < :until
    GROUP BY 1, 2
    """
)


def _buckets(db: DB, site_id: uuid.UUID, span: Range, now: datetime):
    length, step = RANGES[span]
    since = now - length
    params = {"site": site_id, "step": step, "origin": ORIGIN, "since": since}
    found: dict[tuple[str, datetime], Bucket] = {}

    def collect(rows):
        for row in rows:
            # `bucket`, not `t`: SQLAlchemy's Row.t is the row as a tuple.
            found.setdefault((row.target, row.bucket), Bucket()).add(
                row.sum_ms, row.ok, row.total, row.max_ms
            )

    if span == "30d":
        # Raw samples are kept 7 days, so 30 days come from the hourly rollups. Hours the rollup
        # hasn't reached yet (the current one, or more if the job was asleep) come from raw.
        rolled_until = db.scalar(
            select(func.max(PingHourly.hour)).where(
                PingHourly.site_id == site_id, PingHourly.hour >= since
            )
        )
        cutoff = rolled_until + timedelta(hours=1) if rolled_until else since
        collect(db.execute(_HOURLY, {**params, "until": cutoff}))
        collect(db.execute(_RAW, {**params, "since": max(cutoff, since), "until": now}))
    else:
        collect(db.execute(_RAW, {**params, "until": now}))
    return since, step, found


def _outage_out(o: Outage, now: datetime) -> OutageOut:
    end = o.ended_at
    return OutageOut(
        id=o.id,
        started_at=o.started_at,
        ended_at=end,
        duration_s=round(((end or now) - o.started_at).total_seconds(), 1),
        ongoing=end is None,
        cause=o.cause,
        detected_by=o.detected_by,
    )


def _outage_query(site_id: uuid.UUID):
    """Outages of a site, without server-detected ones the agent also measured.

    When the internet drops, the server marks the site unreachable (its own outage) while the
    agent measures the same outage and uploads it later with the exact times and cause. Only the
    agent's record is shown for that period.
    """
    agent_o = aliased(Outage)
    covered = exists().where(
        agent_o.site_id == Outage.site_id,
        agent_o.detected_by == DetectedBy.agent,
        agent_o.started_at < func.coalesce(Outage.ended_at, func.now()),
        func.coalesce(agent_o.ended_at, func.now()) > Outage.started_at,
    )
    return select(Outage).where(
        Outage.site_id == site_id,
        ~and_(Outage.detected_by == DetectedBy.server, covered),
    )


# ---------------------------------------------------------------- endpoints


@router.get("/sites/{site_id}/latency", response_model=LatencyOut)
def latency(
    site_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    range: Range = "24h",  # noqa: A002  (the API's documented parameter name)
    target: TargetChoice = "both",
) -> LatencyOut:
    """Latency and loss over time for the chart, with a summary and the outages in the range."""
    site = require_site(db, user, site_id, Role.viewer)
    return latency_data(db, site.id, range, target, datetime.now(UTC))


def latency_data(
    db: DB, site_id: uuid.UUID, range: Range, target: TargetChoice, now: datetime  # noqa: A002
) -> LatencyOut:
    """The chart's series, summary and outages for one site (also used by the PDF report)."""
    since, step, found = _buckets(db, site_id, range, now)
    targets = ["internet", "gateway"] if target == "both" else [target]
    series: dict[str, list[Point]] = {}
    summary: dict[str, Summary] = {}
    for name in targets:
        keys = sorted(t for (tgt, t) in found if tgt == name)
        series[name] = [found[(name, t)].point(t) for t in keys]
        total = Bucket()
        for t in keys:
            b = found[(name, t)]
            total.add(b.sum_ms, b.ok, b.total, b.max_ms)
        p = total.point(now)
        summary[name] = Summary(
            avg_ms=p.avg_ms,
            max_ms=p.max_ms,
            loss_pct=p.loss_pct if total.total else None,
            samples=p.samples,
        )
    outages = db.scalars(
        _outage_query(site_id)
        .where(Outage.started_at < now, func.coalesce(Outage.ended_at, now) > since)
        .order_by(Outage.started_at)
    )
    return LatencyOut(
        range=range,
        bucket_seconds=int(step.total_seconds()),
        since=since,
        until=now,
        series=series,
        summary=summary,
        outages=[_outage_out(o, now) for o in outages],
    )




@router.get("/sites/{site_id}/outages", response_model=OutageList)
def outages(
    site_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = None,
) -> OutageList:
    """The outage log, newest first (ongoing outages have `ended_at: null`)."""
    site = require_site(db, user, site_id, Role.viewer)
    query = _outage_query(site.id)
    if cursor:
        query = query.where(tuple_(Outage.started_at, Outage.id) < tuple_(*cursors.decode(cursor)))
    rows = list(
        db.scalars(query.order_by(Outage.started_at.desc(), Outage.id.desc()).limit(limit + 1))
    )
    more = len(rows) > limit
    rows = rows[:limit]
    now = datetime.now(UTC)
    return OutageList(
        items=[_outage_out(o, now) for o in rows],
        next_cursor=cursors.encode(rows[-1].started_at, rows[-1].id) if more and rows else None,
    )
