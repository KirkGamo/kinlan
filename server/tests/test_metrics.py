"""Latency history and the outage log (issue #53)."""

from datetime import UTC, datetime, timedelta

from app import jobs
from app.db import get_session_factory
from app.models import DetectedBy, Outage, OutageCause, PingHourly, PingSample, Target

API = "/api/v1"


def floor(dt: datetime, step: timedelta) -> datetime:
    """Bucket start for `dt`, matching the server's alignment (UTC midnight, 2000-01-01)."""
    origin = datetime(2000, 1, 1, tzinfo=UTC)
    return origin + ((dt - origin) // step) * step


def add_samples(site_id, items):
    """items: (ts, target, rtt_ms or None)"""
    with get_session_factory()() as db:
        for ts, target, rtt in items:
            db.add(
                PingSample(
                    site_id=site_id,
                    target=target,
                    ip="8.8.8.8",
                    ts=ts,
                    rtt_ms=rtt,
                    ok=rtt is not None,
                )
            )
        db.commit()


def latency(client, who, site_id, query=""):
    r = client.get(f"{API}/sites/{site_id}/latency{query}", headers=who.h)
    assert r.status_code == 200, r.text
    return r.json()


def test_an_empty_site_has_empty_series(client, ana, home):
    body = latency(client, ana, home["id"])
    assert body["range"] == "24h" and body["bucket_seconds"] == 900
    assert body["series"] == {"internet": [], "gateway": []}
    assert body["summary"]["internet"] == {
        "avg_ms": None,
        "max_ms": None,
        "loss_pct": None,
        "samples": 0,
    }
    assert body["outages"] == []


def test_one_hour_uses_minute_buckets_with_loss(client, ana, home):
    now = datetime.now(UTC)
    minute = floor(now - timedelta(minutes=10), timedelta(minutes=1))
    add_samples(
        home["id"],
        [
            (minute + timedelta(seconds=5), Target.internet, 20.0),
            (minute + timedelta(seconds=15), Target.internet, 40.0),
            (minute + timedelta(seconds=25), Target.internet, None),
            (minute + timedelta(seconds=35), Target.internet, None),
            (minute + timedelta(seconds=5), Target.gateway, 2.0),
            (now - timedelta(hours=2), Target.internet, 999.0),  # outside the hour
        ],
    )
    body = latency(client, ana, home["id"], "?range=1h")
    assert body["bucket_seconds"] == 60
    [point] = body["series"]["internet"]
    assert datetime.fromisoformat(point["t"]) == minute
    assert (point["avg_ms"], point["max_ms"], point["loss_pct"], point["samples"]) == (
        30.0,
        40.0,
        50.0,
        4,
    )
    assert body["summary"]["internet"]["avg_ms"] == 30.0
    assert body["series"]["gateway"][0]["avg_ms"] == 2.0


def test_target_can_be_one_line(client, ana, home):
    add_samples(home["id"], [(datetime.now(UTC) - timedelta(minutes=5), Target.gateway, 3.0)])
    body = latency(client, ana, home["id"], "?target=gateway")
    assert list(body["series"]) == ["gateway"] and body["series"]["gateway"][0]["avg_ms"] == 3.0


def test_a_bucket_where_every_ping_was_lost_has_no_average(client, ana, home):
    t = datetime.now(UTC) - timedelta(minutes=30)
    add_samples(
        home["id"], [(t, Target.internet, None), (t + timedelta(seconds=10), Target.internet, None)]
    )
    [point] = latency(client, ana, home["id"], "?range=24h")["series"]["internet"]
    assert point["avg_ms"] is None and point["loss_pct"] == 100.0


def test_thirty_days_merges_hourly_rollups_with_the_raw_tail(client, ana, home):
    now = datetime.now(UTC)
    this_hour = now.replace(minute=0, second=0, microsecond=0)
    old = this_hour - timedelta(days=10)
    with get_session_factory()() as db:
        # Ten days ago: one rolled-up hour, 10 pings averaging 50 ms with 20 % loss (8 answered).
        db.add(
            PingHourly(
                site_id=home["id"],
                target=Target.internet,
                hour=old,
                avg_ms=50.0,
                min_ms=40.0,
                max_ms=80.0,
                loss_pct=20.0,
                samples=10,
            )
        )
        db.commit()
    # Recent raw pings (not rolled up yet) must still appear.
    add_samples(home["id"], [(now - timedelta(minutes=2), Target.internet, 10.0)])
    body = latency(client, ana, home["id"], "?range=30d")
    assert body["bucket_seconds"] == 6 * 3600
    points = body["series"]["internet"]
    assert len(points) == 2
    old_point = next(p for p in points if datetime.fromisoformat(p["t"]) <= old)
    assert (
        old_point["avg_ms"],
        old_point["max_ms"],
        old_point["loss_pct"],
        old_point["samples"],
    ) == (50.0, 80.0, 20.0, 10)
    # Summary weights by answered pings: (8 x 50 + 1 x 10) / 9
    assert body["summary"]["internet"]["avg_ms"] == round((8 * 50 + 10) / 9, 2)


def test_thirty_days_after_the_rollup_job_does_not_double_count(client, ana, home):
    now = datetime.now(UTC)
    hour_ago = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    add_samples(
        home["id"], [(hour_ago + timedelta(minutes=m), Target.internet, 20.0) for m in range(6)]
    )
    with get_session_factory()() as db:
        jobs.rollup_hourly(db, now)
    body = latency(client, ana, home["id"], "?range=30d")
    assert body["summary"]["internet"]["samples"] == 6


def test_unknown_range_is_rejected(client, ana, home):
    r = client.get(f"{API}/sites/{home['id']}/latency?range=1y", headers=ana.h)
    assert r.status_code == 400 and r.json()["error"]["code"] == "validation_error"


# ---------------------------------------------------------------- outages


def add_outage(site_id, start, end, cause, by):
    with get_session_factory()() as db:
        db.add(Outage(site_id=site_id, started_at=start, ended_at=end, cause=cause, detected_by=by))
        db.commit()


def test_outage_log_prefers_the_agents_measurement(client, ana, home):
    now = datetime.now(UTC)
    start = now - timedelta(hours=3)
    # The same outage seen twice: the server noticed silence, the agent measured it exactly.
    add_outage(
        home["id"],
        start + timedelta(minutes=2),
        start + timedelta(minutes=9),
        OutageCause.unknown,
        DetectedBy.server,
    )
    add_outage(
        home["id"],
        start,
        start + timedelta(minutes=7, seconds=12),
        OutageCause.isp,
        DetectedBy.agent,
    )
    # A separate power cut the agent couldn't measure: only the server's record exists.
    add_outage(
        home["id"], now - timedelta(minutes=20), None, OutageCause.unknown, DetectedBy.server
    )
    items = client.get(f"{API}/sites/{home['id']}/outages", headers=ana.h).json()["items"]
    assert [(o["detected_by"], o["cause"], o["ongoing"]) for o in items] == [
        ("server", "unknown", True),
        ("agent", "isp", False),
    ]
    assert items[1]["duration_s"] == 432.0
    chart = latency(client, ana, home["id"])
    assert [o["cause"] for o in chart["outages"]] == ["isp", "unknown"]


def test_outage_log_pages(client, ana, home):
    now = datetime.now(UTC)
    for i in range(3):
        start = now - timedelta(days=i + 1)
        add_outage(
            home["id"], start, start + timedelta(minutes=1), OutageCause.isp, DetectedBy.agent
        )
    url = f"{API}/sites/{home['id']}/outages"
    first = client.get(f"{url}?limit=2", headers=ana.h).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = client.get(f"{url}?limit=2&cursor={first['next_cursor']}", headers=ana.h).json()
    assert len(second["items"]) == 1 and second["next_cursor"] is None


def test_outsiders_get_not_found(client, ana, eve, home):
    for path in (f"/sites/{home['id']}/latency", f"/sites/{home['id']}/outages"):
        r = client.get(f"{API}{path}", headers=eve.h)
        assert r.status_code == 404 and r.json()["error"]["code"] == "site_not_found", path
