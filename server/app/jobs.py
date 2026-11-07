"""Scheduled jobs (plan, Section 4.5), run in-process by APScheduler (Render runs one instance).

| Job              | Every  | Work                                                         |
|------------------|--------|--------------------------------------------------------------|
| check_heartbeats | 1 min  | mark silent sites unreachable and raise the alert            |
| rollup_hourly    | 1 h    | combine raw samples into ping_hourly                         |
| retention        | daily  | delete old samples, rollups, alerts, codes, tokens, batches  |

Each job is a plain function taking a session, so tests call them directly. ``push_receipts``
joins when Expo push arrives (Sprint 3).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app import alerts
from app.models import (
    Alert,
    AlertSettings,
    IngestBatch,
    Invite,
    PairingCode,
    PingHourly,
    PingSample,
    RefreshToken,
    Report,
    Site,
    SiteStatus,
)

log = logging.getLogger("kinlan.jobs")

RAW_SAMPLES_DAYS = 7
HOURLY_DAYS = 90
RESOLVED_ALERTS_DAYS = 90
INGEST_BATCH_DAYS = 2
REPORT_DAYS = 30
DEAD_TOKEN_DAYS = 30
ROLLUP_LOOKBACK = timedelta(hours=3)  # re-roll recent hours so late (buffered) samples count


def check_heartbeats(db: Session, now: datetime | None = None) -> int:
    """Sites whose agent has been silent longer than their offline threshold go unreachable."""
    now = now or datetime.now(UTC)
    rows = db.execute(
        select(Site, AlertSettings.offline_seconds)
        .outerjoin(AlertSettings, AlertSettings.site_id == Site.id)
        .where(Site.status.in_([SiteStatus.online, SiteStatus.degraded]))
    ).all()
    changed = 0
    for site, offline_seconds in rows:
        limit = timedelta(seconds=offline_seconds or 120)
        if site.last_seen_at is None or site.last_seen_at < now - limit:
            alerts.went_unreachable(db, site, now)
            changed += 1
    db.commit()
    return changed


_ROLLUP_SQL = text(
    """
    INSERT INTO ping_hourly (site_id, target, hour, avg_ms, min_ms, max_ms, loss_pct, samples)
    SELECT site_id, target, date_trunc('hour', ts) AS hour,
           avg(rtt_ms) FILTER (WHERE ok), min(rtt_ms) FILTER (WHERE ok),
           max(rtt_ms) FILTER (WHERE ok),
           100.0 * count(*) FILTER (WHERE NOT ok) / count(*), count(*)
    FROM ping_samples
    WHERE ts >= :since AND ts < :until
    GROUP BY site_id, target, date_trunc('hour', ts)
    ON CONFLICT (site_id, target, hour) DO UPDATE SET
        avg_ms = excluded.avg_ms, min_ms = excluded.min_ms, max_ms = excluded.max_ms,
        loss_pct = excluded.loss_pct, samples = excluded.samples
    """
)


def rollup_hourly(db: Session, now: datetime | None = None) -> int:
    """Roll up the last few *completed* hours (idempotent, so it can run any number of times)."""
    now = now or datetime.now(UTC)
    until = now.replace(minute=0, second=0, microsecond=0)
    result = db.execute(_ROLLUP_SQL, {"since": until - ROLLUP_LOOKBACK, "until": until})
    db.commit()
    return result.rowcount


def retention(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Delete what the plan says to stop keeping; returns how many rows each step removed."""
    now = now or datetime.now(UTC)

    def days(n: int) -> datetime:
        return now - timedelta(days=n)

    steps = {
        "ping_samples": delete(PingSample).where(PingSample.ts < days(RAW_SAMPLES_DAYS)),
        "ping_hourly": delete(PingHourly).where(PingHourly.hour < days(HOURLY_DAYS)),
        "alerts": delete(Alert).where(
            Alert.resolved_at.is_not(None), Alert.resolved_at < days(RESOLVED_ALERTS_DAYS)
        ),
        "ingest_batches": delete(IngestBatch).where(
            IngestBatch.received_at < days(INGEST_BATCH_DAYS)
        ),
        "reports": delete(Report).where(Report.created_at < days(REPORT_DAYS)),
        "invites": delete(Invite).where(Invite.used_at.is_(None), Invite.expires_at < now),
        "pairing_codes": delete(PairingCode).where(PairingCode.expires_at < now),
        # Expired tokens go at once; revoked ones stay a while so reuse is still detected.
        "refresh_tokens": delete(RefreshToken).where(
            (RefreshToken.expires_at < now) | (RefreshToken.revoked_at < days(DEAD_TOKEN_DAYS))
        ),
    }
    removed = {name: db.execute(stmt).rowcount for name, stmt in steps.items()}
    db.commit()
    return removed


def start_scheduler():
    """Start the jobs in a background thread; returns the scheduler (call .shutdown() to stop)."""
    from apscheduler.schedulers.background import BackgroundScheduler

    from app.db import get_session_factory

    def run(job):
        def wrapped():
            with get_session_factory()() as db:
                try:
                    job(db)
                except Exception:
                    log.exception("job %s failed", job.__name__)
                    db.rollback()

        wrapped.__name__ = job.__name__
        return wrapped

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(run(check_heartbeats), "interval", minutes=1, id="check_heartbeats")
    scheduler.add_job(run(rollup_hourly), "cron", minute=5, id="rollup_hourly")
    scheduler.add_job(run(retention), "cron", hour=19, minute=30, id="retention")  # 03:30 PHT
    scheduler.start()
    log.info("scheduler started: %s", ", ".join(j.id for j in scheduler.get_jobs()))
    return scheduler
