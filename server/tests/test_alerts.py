"""Alert engine, alert endpoints and scheduled jobs (Sections 4.4 and 4.5)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app import alerts, jobs
from app.db import get_session_factory
from app.models import (
    Alert,
    AlertSettings,
    IngestBatch,
    Outage,
    PingHourly,
    PingSample,
    RefreshToken,
    Site,
    SiteStatus,
    Target,
)
from tests.agent_fixtures import PC, PHONE, ROUTER, batch, sample, scan

API = "/api/v1"


def ingest(client, agent, **parts):
    r = client.post(f"{API}/agent/ingest", json=batch(**parts), headers=agent["h"])
    assert r.status_code == 200, r.text
    return r.json()


def open_alerts(site_id) -> list[Alert]:
    with get_session_factory()() as db:
        return list(
            db.scalars(
                select(Alert)
                .where(Alert.site_id == site_id, Alert.resolved_at.is_(None))
                .order_by(Alert.created_at)
            )
        )


# ---------------------------------------------------------------- new devices and ports


def test_strangers_after_the_baseline_raise_a_new_device_alert(client, agent, home):
    ingest(client, agent, devices=scan(ROUTER, PC))
    assert open_alerts(home["id"]) == []  # the baseline scan never alerts
    ingest(client, agent, devices=scan(ROUTER, PC, PHONE))
    ingest(client, agent, devices=scan(ROUTER, PC, PHONE))  # seen again: not new
    [alert] = open_alerts(home["id"])
    assert alert.type == "new_device" and alert.severity == "warning"
    assert alert.title == "Someone new joined: Galaxy-A15"
    assert "Whose is it?" in alert.body and "Samsung" in alert.body


def test_new_device_alerts_can_be_turned_off(client, agent, home):
    with get_session_factory()() as db:
        db.get(AlertSettings, home["id"]).notify_new_device = False
        db.commit()
    ingest(client, agent, devices=scan(ROUTER))
    ingest(client, agent, devices=scan(ROUTER, PHONE))
    assert open_alerts(home["id"]) == []


def test_risky_ports_alert_once_and_telnet_is_critical(client, agent, home):
    ingest(client, agent, devices=scan(ROUTER, PC))
    telnet = {"mac": ROUTER[0], "port": 23, "service": "telnet"}
    rdp = {"mac": PC[0], "port": 3389, "service": "rdp"}
    ingest(client, agent, port_findings=[telnet, rdp])
    ingest(client, agent, port_findings=[telnet, rdp])
    found = {a.title: a.severity for a in open_alerts(home["id"])}
    assert found == {
        "TELNET is open on China Mobile IOT": "critical",
        "RDP is open on DESKTOP-01": "warning",
    }


# ---------------------------------------------------------------- unreachable and back online


def test_a_silent_site_goes_unreachable_then_comes_back(client, agent, home):
    ingest(client, agent, samples=[sample(0)])
    with get_session_factory()() as db:
        db.get(Site, home["id"]).last_seen_at = datetime.now(UTC) - timedelta(minutes=3)
        db.commit()
        assert jobs.check_heartbeats(db) == 1
        assert jobs.check_heartbeats(db) == 0  # already unreachable: no second alert
        site = db.get(Site, home["id"])
        assert site.status == SiteStatus.unreachable
        server_outage = db.scalar(select(Outage).where(Outage.detected_by == "server"))
        assert server_outage.ended_at is None
    [alert] = open_alerts(home["id"])
    assert alert.type == "unreachable" and alert.severity == "critical"
    assert alert.title == "Home is unreachable" and "power outage" in alert.body

    ingest(client, agent, samples=[sample(0)])
    [back] = open_alerts(home["id"])
    assert back.type == "back_online" and back.title == "Home is back online"
    with get_session_factory()() as db:
        assert db.get(Site, home["id"]).status == SiteStatus.online
        assert db.scalar(select(Outage).where(Outage.detected_by == "server")).ended_at is not None


def test_back_online_uses_the_agents_measured_outage(client, agent, home):
    start = datetime.now(UTC) - timedelta(minutes=20)
    outage = {
        "started_at": start.isoformat(),
        "cause": "isp",
        "ended_at": (start + timedelta(minutes=4, seconds=12)).isoformat(),
    }
    ingest(client, agent, outages=[outage])
    [alert] = open_alerts(home["id"])
    assert alert.title == "Home is back online after 4 min 12 s"
    assert "internet provider outage" in alert.body


def test_pending_sites_are_not_marked_unreachable(client, home):
    with get_session_factory()() as db:
        assert jobs.check_heartbeats(db) == 0
        assert db.get(Site, home["id"]).status == SiteStatus.pending


def test_the_offline_threshold_is_per_site(client, agent, home):
    ingest(client, agent, samples=[sample(0)])
    with get_session_factory()() as db:
        db.get(AlertSettings, home["id"]).offline_seconds = 600
        db.get(Site, home["id"]).last_seen_at = datetime.now(UTC) - timedelta(minutes=5)
        db.commit()
        assert jobs.check_heartbeats(db) == 0


# ---------------------------------------------------------------- latency and loss


def _samples(db, site_id, now, values):
    for i, rtt in enumerate(values):
        db.add(
            PingSample(
                site_id=site_id,
                target=Target.internet,
                ip="8.8.8.8",
                ts=now - timedelta(seconds=10 * (i + 1)),
                rtt_ms=rtt,
                ok=rtt is not None,
            )
        )


def test_slow_and_lossy_internet_alerts_and_resolves(client, home):
    now = datetime.now(UTC)
    with get_session_factory()() as db:
        site = db.get(Site, home["id"])
        _samples(db, site.id, now, [300.0] * 6 + [None] * 4)  # avg 300 ms, 40 % loss
        db.flush()
        alerts.thresholds(db, site, now)
        db.commit()
        assert {a.type for a in open_alerts(site.id)} == {"high_latency", "packet_loss"}
        later = now + timedelta(minutes=10)
        _samples(db, site.id, later, [20.0] * 10)
        db.flush()
        alerts.thresholds(db, site, later)
        db.commit()
    assert open_alerts(home["id"]) == []


def test_too_few_samples_never_alert(client, home):
    now = datetime.now(UTC)
    with get_session_factory()() as db:
        site = db.get(Site, home["id"])
        _samples(db, site.id, now, [None] * 3)
        db.flush()
        alerts.thresholds(db, site, now)
        db.commit()
    assert open_alerts(home["id"]) == []


def test_an_open_alert_is_not_repeated_within_30_minutes(client, home):
    now = datetime.now(UTC)
    with get_session_factory()() as db:
        site = db.get(Site, home["id"])
        first = alerts.raise_alert(db, site, "high_latency", "warning", "Slow", "x", now=now)
        again = alerts.raise_alert(
            db, site, "high_latency", "warning", "Slow", "x", now=now + timedelta(minutes=10)
        )
        later = alerts.raise_alert(
            db, site, "high_latency", "warning", "Slow", "x", now=now + timedelta(minutes=31)
        )
        db.commit()
    assert first is not None and again is None and later is not None


def test_duration_words():
    assert alerts.duration_words(42) == "42 s"
    assert alerts.duration_words(252) == "4 min 12 s"
    assert alerts.duration_words(600) == "10 min"
    assert alerts.duration_words(3 * 3600 + 120) == "3 h 2 min"


# ---------------------------------------------------------------- endpoints


def _seed_alerts(site_id, n):
    now = datetime.now(UTC)
    with get_session_factory()() as db:
        for i in range(n):
            db.add(
                Alert(
                    site_id=site_id,
                    type="new_device",
                    severity="warning",
                    title=f"A{i}",
                    body="b",
                    subject_ref=str(i),
                    created_at=now - timedelta(minutes=n - i),
                )
            )
        db.commit()


def test_alerts_list_newest_first_with_pagination(client, ana, home):
    _seed_alerts(home["id"], 3)
    page1 = client.get(f"{API}/sites/{home['id']}/alerts?limit=2", headers=ana.h).json()
    assert [a["title"] for a in page1["items"]] == ["A2", "A1"] and page1["next_cursor"]
    page2 = client.get(
        f"{API}/sites/{home['id']}/alerts?limit=2&cursor={page1['next_cursor']}", headers=ana.h
    ).json()
    assert [a["title"] for a in page2["items"]] == ["A0"] and page2["next_cursor"] is None
    bad = client.get(f"{API}/sites/{home['id']}/alerts?cursor=nonsense", headers=ana.h)
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "bad_cursor"


def test_acknowledging_moves_an_alert_out_of_open(client, ana, jun, home):
    _seed_alerts(home["id"], 1)
    code = client.post(
        f"{API}/circles/{home['circle_id']}/invites", json={"role": "viewer"}, headers=ana.h
    ).json()["code"]
    client.post(f"{API}/invites/accept", json={"code": code}, headers=jun.h)
    alert_id = client.get(f"{API}/sites/{home['id']}/alerts", headers=jun.h).json()["items"][0][
        "id"
    ]
    assert client.post(f"{API}/alerts/{alert_id}/ack", headers=jun.h).status_code == 403
    r = client.post(f"{API}/alerts/{alert_id}/ack", headers=ana.h)
    assert r.status_code == 200 and r.json()["acked_by"] == ana.id
    first_ack = r.json()["acked_at"]
    assert (
        client.post(f"{API}/alerts/{alert_id}/ack", headers=ana.h).json()["acked_at"] == first_ack
    )
    open_items = client.get(f"{API}/sites/{home['id']}/alerts?status=open", headers=ana.h).json()
    done = client.get(f"{API}/sites/{home['id']}/alerts?status=resolved", headers=ana.h).json()
    assert open_items["items"] == [] and len(done["items"]) == 1


def test_alert_settings_read_and_change(client, ana, jun, home):
    url = f"{API}/sites/{home['id']}/alert-settings"
    assert client.get(url, headers=ana.h).json() == {
        "latency_ms": 150.0,
        "loss_pct": 5.0,
        "offline_seconds": 120,
        "notify_new_device": True,
    }
    r = client.patch(url, json={"latency_ms": 200, "notify_new_device": False}, headers=ana.h)
    assert (
        r.status_code == 200 and r.json()["latency_ms"] == 200 and not r.json()["notify_new_device"]
    )
    assert client.patch(url, json={"offline_seconds": 5}, headers=ana.h).status_code == 400


def test_outsiders_cannot_see_or_touch_alerts(client, ana, eve, home):
    _seed_alerts(home["id"], 1)
    alert_id = client.get(f"{API}/sites/{home['id']}/alerts", headers=ana.h).json()["items"][0][
        "id"
    ]
    for method, path in [
        ("get", f"/sites/{home['id']}/alerts"),
        ("get", f"/sites/{home['id']}/alert-settings"),
        ("patch", f"/sites/{home['id']}/alert-settings"),
        ("post", f"/alerts/{alert_id}/ack"),
    ]:
        kwargs = {"headers": eve.h, **({"json": {}} if method == "patch" else {})}
        r = getattr(client, method)(f"{API}{path}", **kwargs)
        assert r.status_code == 404, path


# ---------------------------------------------------------------- jobs


def test_rollup_combines_last_hours_samples_and_is_idempotent(client, home):
    now = datetime.now(UTC).replace(minute=20, second=0, microsecond=0)
    hour = now.replace(minute=0) - timedelta(hours=1)
    with get_session_factory()() as db:
        for i, rtt in enumerate([10.0, 20.0, 30.0, None]):
            db.add(
                PingSample(
                    site_id=home["id"],
                    target=Target.internet,
                    ip="8.8.8.8",
                    ts=hour + timedelta(minutes=i),
                    rtt_ms=rtt,
                    ok=rtt is not None,
                )
            )
        db.add(
            PingSample(
                site_id=home["id"],
                target=Target.internet,
                ip="8.8.8.8",
                ts=now - timedelta(minutes=5),
                rtt_ms=99.0,
                ok=True,
            )
        )  # hour not over
        db.commit()
        jobs.rollup_hourly(db, now)
        jobs.rollup_hourly(db, now)
        rows = list(db.scalars(select(PingHourly)))
    assert len(rows) == 1
    row = rows[0]
    assert (row.avg_ms, row.min_ms, row.max_ms, row.loss_pct, row.samples) == (
        20.0,
        10.0,
        30.0,
        25.0,
        4,
    )


def test_retention_deletes_only_what_is_old(client, ana, agent, home):
    now = datetime.now(UTC)
    with get_session_factory()() as db:
        db.add(
            PingSample(
                site_id=home["id"],
                target=Target.internet,
                ip="8.8.8.8",
                ts=now - timedelta(days=8),
                rtt_ms=10,
                ok=True,
            )
        )
        db.add(
            PingSample(
                site_id=home["id"],
                target=Target.internet,
                ip="8.8.8.8",
                ts=now - timedelta(days=1),
                rtt_ms=10,
                ok=True,
            )
        )
        db.add(
            IngestBatch(
                batch_id="00000000-0000-4000-8000-000000000001",
                agent_id=agent["agent_id"],
                received_at=now - timedelta(days=3),
            )
        )
        token = db.scalar(select(RefreshToken))
        token.revoked_at = now - timedelta(days=31)
        db.commit()
        removed = jobs.retention(db, now)
        assert removed["ping_samples"] == 1 and removed["ingest_batches"] == 1
        assert removed["refresh_tokens"] >= 1
        assert db.scalar(select(func.count()).select_from(PingSample)) == 1
