"""PDF reports (#88; plan, Sections 4.3 and 4.7): content, download links and who can see them."""

import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app import jobs, reports
from app.db import get_session_factory
from app.models import Device, Report, Site
from app.routers.reports import download_token
from tests.agent_fixtures import PC, PHONE, ROUTER, batch, iso, sample, scan

API = "/api/v1"


def join(client, owner, circle_id, person, role="viewer"):
    code = client.post(
        f"{API}/circles/{circle_id}/invites", json={"role": role}, headers=owner.h
    ).json()["code"]
    assert client.post(f"{API}/invites/accept", json={"code": code}, headers=person.h).is_success


def busy_day(client, agent):
    """A day with pings, a stranger, an open Telnet port, an outage and a ping test."""
    ingest = lambda **parts: client.post(  # noqa: E731
        f"{API}/agent/ingest", headers=agent["h"], json=batch(**parts)
    )
    ingest(devices=scan(ROUTER, PC))  # baseline
    ingest(devices=scan(ROUTER, PC, PHONE))  # a stranger joins
    samples = [sample(m, rtt=18.0 + m % 5) for m in range(1, 240, 2)]
    samples += [sample(m, target="gateway", ip="192.168.1.1", rtt=2.5) for m in range(1, 240, 2)]
    start = datetime.now(UTC) - timedelta(hours=2)
    ingest(
        samples=samples,
        port_findings=[{"mac": ROUTER[0], "port": 23, "service": "telnet"}],
        outages=[
            {
                "started_at": iso(start),
                "ended_at": iso(start + timedelta(minutes=4, seconds=12)),
                "cause": "isp",
            }
        ],
    )


def test_a_member_makes_a_report_and_downloads_it(client, ana, jun, agent, home):
    busy_day(client, agent)
    join(client, ana, home["circle_id"], jun)  # viewers may read reports too
    r = client.post(f"{API}/sites/{home['id']}/reports", json={"range": "7d"}, headers=jun.h)
    assert r.status_code == 201, r.text
    made = r.json()
    assert made["range"] == "7d" and made["filename"].startswith("KinLAN-Home-7d-")
    pdf = client.get(made["download_url"])
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF") and len(pdf.content) > 20_000  # text, tables and chart
    assert 'filename="KinLAN-Home-7d-' in pdf.headers["content-disposition"]


def test_the_report_gathers_every_section(client, agent, home):
    busy_day(client, agent)
    with get_session_factory()() as db:
        data = reports.gather(db, db.get(Site, home["id"]), "24h")
    assert [p.name for p in data.pings[:2]] == ["Router", "Internet"]
    assert data.pings[1].avg_ms is not None and data.pings[0].avg_ms == 2.5
    assert len(data.devices) == 3 and len(data.latency.outages) == 1
    assert [f.port for _, f in data.findings] == [23]
    recs = [title for title, _ in reports.recommendations(data)]
    found = recs[: len(recs) - len(reports.ROUTER_ADVICE)]
    assert any("Telnet" in t or "port 23" in t.lower() or "23" in t for t in found)
    assert recs[-5:] == [t for t, _ in reports.ROUTER_ADVICE]  # the fixed advice always closes it


def test_a_quiet_site_still_gets_a_report(client, ana, home):
    """No agent yet: every section says so instead of failing."""
    r = client.post(f"{API}/sites/{home['id']}/reports", json={"range": "24h"}, headers=ana.h)
    assert r.status_code == 201
    assert client.get(r.json()["download_url"]).content.startswith(b"%PDF")


def test_ping_tests_in_the_range_are_listed(client, ana, agent, home):
    busy_day(client, agent)
    with get_session_factory()() as db:
        phone = db.scalar(select(Device).where(Device.mac == PHONE[0]))
        phone_id = phone.id
    cmd = client.post(
        f"{API}/sites/{home['id']}/commands",
        json={"type": "ping_test", "params": {"device_id": str(phone_id), "count": 5}},
        headers=ana.h,
    ).json()
    client.get(f"{API}/agent/commands?wait=0", headers=agent["h"])
    result = {"sent": 5, "received": 4, "loss_pct": 20, "min_ms": 3, "avg_ms": 6.5,
              "max_ms": 12, "jitter_ms": 2}
    client.post(f"{API}/agent/commands/{cmd['id']}/result", headers=agent["h"],
                json={"ok": True, "result": result})
    with get_session_factory()() as db:
        data = reports.gather(db, db.get(Site, home["id"]), "24h")
    [row] = data.pings[2:]
    assert row.name == "Galaxy-A15" and row.tests == 1 and row.loss_pct == 20


def test_outsiders_cannot_make_or_read_reports(client, ana, eve, home):
    outsider = client.post(f"{API}/sites/{home['id']}/reports", json={}, headers=eve.h)
    assert outsider.status_code == 404
    made = client.post(f"{API}/sites/{home['id']}/reports", json={}, headers=ana.h).json()
    assert client.get(f"{API}/reports/{made['id']}", headers=eve.h).status_code == 404
    fresh = client.get(f"{API}/reports/{made['id']}", headers=ana.h).json()
    assert fresh["download_url"].startswith(f"/api/v1/reports/{made['id']}.pdf?token=")


def test_download_links_are_signed_per_report_and_expire(client, ana, home):
    a = client.post(f"{API}/sites/{home['id']}/reports", json={}, headers=ana.h).json()
    b = client.post(f"{API}/sites/{home['id']}/reports", json={}, headers=ana.h).json()
    token_a = a["download_url"].split("token=")[1]
    swapped = client.get(f"{API}/reports/{b['id']}.pdf?token={token_a}")
    assert swapped.status_code == 403  # a link only opens its own report
    stale = download_token(a["id"], now=time.time() - 3600)
    expired = client.get(f"{API}/reports/{a['id']}.pdf?token={stale}")
    assert expired.status_code == 403 and expired.json()["error"]["code"] == "link_expired"
    assert client.get(f"{API}/reports/{a['id']}.pdf?token=nonsense").status_code == 403
    assert client.get(f"{API}/reports/{a['id']}.pdf").status_code == 400  # no token at all


def test_reports_are_kept_thirty_days(client, ana, home):
    made = client.post(f"{API}/sites/{home['id']}/reports", json={}, headers=ana.h).json()
    with get_session_factory()() as db:
        db.get(Report, made["id"]).created_at = datetime.now(UTC) - timedelta(days=31)
        db.commit()
        assert jobs.retention(db)["reports"] == 1
