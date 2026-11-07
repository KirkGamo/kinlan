"""Sites, the site summary and pairing codes, plus isolation between Circles (Sections 3.6, 4.3,
4.6)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db import get_session_factory
from app.models import (
    Alert,
    AlertSettings,
    Device,
    Outage,
    PairingCode,
    PingSample,
    PortFinding,
    Target,
)
from app.security import keyed_hash

API = "/api/v1"


def circle_with(client, owner, *members_roles):
    """A Circle owned by `owner`, with each (person, role) joined through an invite."""
    circle = client.post(f"{API}/circles", json={"name": "Dela Cruz Home"}, headers=owner.h).json()
    for person, role in members_roles:
        code = client.post(
            f"{API}/circles/{circle['id']}/invites", json={"role": role}, headers=owner.h
        ).json()["code"]
        joined = client.post(f"{API}/invites/accept", json={"code": code}, headers=person.h)
        assert joined.is_success
    return circle["id"]


def make_site(client, who, circle, name="Home", **extra):
    return client.post(f"{API}/circles/{circle}/sites", json={"name": name, **extra}, headers=who.h)


# ---------------------------------------------------------------- sites


def test_admin_creates_a_pending_site_with_default_alert_settings(client, ana, jun):
    circle = circle_with(client, ana, (jun, "admin"))
    r = make_site(client, jun, circle)
    assert r.status_code == 201
    site = r.json()
    assert site["status"] == "pending" and site["timezone"] == "Asia/Manila"
    assert site["last_seen_at"] is None and site["gateway_ip"] is None
    with get_session_factory()() as db:
        settings = db.get(AlertSettings, site["id"])
        assert (settings.latency_ms, settings.loss_pct, settings.offline_seconds) == (150, 5, 120)
        assert settings.notify_new_device is True


def test_viewers_cannot_create_sites(client, ana, jun):
    circle = circle_with(client, ana, (jun, "viewer"))
    r = make_site(client, jun, circle)
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


def test_unknown_time_zones_are_rejected(client, ana):
    circle = circle_with(client, ana)
    r = make_site(client, ana, circle, timezone="Mars/Olympus")
    assert r.status_code == 400 and r.json()["error"]["message"].startswith("timezone")


def test_list_get_and_rename(client, ana, jun):
    circle = circle_with(client, ana, (jun, "viewer"))
    home = make_site(client, ana, circle).json()["id"]
    make_site(client, ana, circle, "Lola's house")
    names = [
        s["name"]
        for s in client.get(f"{API}/circles/{circle}/sites", headers=jun.h).json()["items"]
    ]
    assert names == ["Home", "Lola's house"]
    assert client.get(f"{API}/sites/{home}", headers=jun.h).json()["name"] == "Home"
    assert client.patch(f"{API}/sites/{home}", json={"name": "x"}, headers=jun.h).status_code == 403
    r = client.patch(
        f"{API}/sites/{home}", json={"name": "Main house", "timezone": "Asia/Tokyo"}, headers=ana.h
    )
    assert r.status_code == 200 and (r.json()["name"], r.json()["timezone"]) == (
        "Main house",
        "Asia/Tokyo",
    )


def test_only_owners_delete_a_site_and_its_history(client, ana, jun):
    circle = circle_with(client, ana, (jun, "admin"))
    site = make_site(client, ana, circle).json()["id"]
    with get_session_factory()() as db:
        db.add(Device(site_id=site, mac="a8:9c:ed:00:00:01"))
        db.commit()
    assert client.delete(f"{API}/sites/{site}", headers=jun.h).status_code == 403
    assert client.delete(f"{API}/sites/{site}", headers=ana.h).status_code == 204
    assert client.get(f"{API}/sites/{site}", headers=ana.h).status_code == 404
    with get_session_factory()() as db:
        assert db.scalar(select(Device)) is None


# ---------------------------------------------------------------- summary


def test_a_new_site_summary_is_an_a_with_nothing_measured(client, ana):
    site = make_site(client, ana, circle_with(client, ana)).json()["id"]
    s = client.get(f"{API}/sites/{site}/summary", headers=ana.h).json()
    assert (s["score"], s["grade"], s["deductions"]) == (100, "A", [])
    assert s["internet"] is None and s["gateway"] is None
    assert (s["devices_total"], s["needs_review"], s["open_alerts"]) == (0, 0, 0)


def test_summary_measures_the_last_24_hours(client, ana):
    site = make_site(client, ana, circle_with(client, ana)).json()["id"]
    now = datetime.now(UTC)
    with get_session_factory()() as db:
        # 10 internet pings: 8 ok at 250 ms, 2 lost → 20% loss; one old lost ping is ignored.
        for i in range(10):
            ok = i < 8
            db.add(
                PingSample(
                    site_id=site,
                    target=Target.internet,
                    ip="8.8.8.8",
                    ts=now - timedelta(minutes=10 - i),
                    rtt_ms=250.0 if ok else None,
                    ok=ok,
                )
            )
        db.add(
            PingSample(
                site_id=site,
                target=Target.internet,
                ip="8.8.8.8",
                ts=now - timedelta(days=2),
                rtt_ms=None,
                ok=False,
            )
        )
        db.add(
            PingSample(
                site_id=site,
                target=Target.gateway,
                ip="192.168.1.1",
                ts=now - timedelta(seconds=5),
                rtt_ms=2.0,
                ok=True,
            )
        )
        db.add(
            Outage(
                site_id=site,
                started_at=now - timedelta(minutes=7),
                detected_by="agent",
                cause="isp",
            )
        )
        baseline = Device(site_id=site, mac="64:f8:8a:00:00:01", baseline=True, online=True)
        stranger = Device(site_id=site, mac="a8:9c:ed:00:00:02", baseline=False, online=True)
        printer = Device(site_id=site, mac="3c:2a:f4:00:00:03", baseline=True, online=False)
        db.add_all([baseline, stranger, printer])
        db.flush()
        db.add(PortFinding(device_id=printer.id, port=23, service="telnet"))
        db.add(
            Alert(
                site_id=site,
                type="new_device",
                severity="warning",
                title="Someone new joined",
                body="Galaxy-A15",
            )
        )
        db.commit()
    s = client.get(f"{API}/sites/{site}/summary", headers=ana.h).json()
    points = {d["factor"]: d["points"] for d in s["deductions"]}
    assert points == {"latency": 20, "loss": 30, "outages": 5, "devices": 5, "ports": 10}
    assert (s["score"], s["grade"]) == (30, "F")
    assert s["grade_summary"] == "Some data is getting lost on the way to the internet."
    # The newest internet ping is one of the lost ones: "no reply", not a stale number.
    assert s["internet"]["ok"] is False and s["internet"]["rtt_ms"] is None
    assert s["gateway"]["rtt_ms"] == 2.0
    assert (s["devices_total"], s["devices_online"], s["needs_review"]) == (3, 2, 1)
    assert s["open_alerts"] == 1 and s["open_outage_since"] is not None


# ---------------------------------------------------------------- pairing codes


def test_admin_gets_a_six_digit_code_valid_for_ten_minutes(client, ana, jun):
    circle = circle_with(client, ana, (jun, "admin"))
    site = make_site(client, ana, circle).json()["id"]
    r = client.post(f"{API}/sites/{site}/pairing-code", headers=jun.h)
    assert r.status_code == 201
    code, expires = r.json()["code"], datetime.fromisoformat(r.json()["expires_at"])
    assert len(code) == 6 and code.isdigit()
    assert timedelta(minutes=9) < expires - datetime.now(UTC) <= timedelta(minutes=10)
    with get_session_factory()() as db:
        row = db.scalar(select(PairingCode))
        assert row.code_hash == keyed_hash(code) and code not in row.code_hash


def test_a_new_code_cancels_the_previous_unused_one(client, ana):
    site = make_site(client, ana, circle_with(client, ana)).json()["id"]
    first = client.post(f"{API}/sites/{site}/pairing-code", headers=ana.h).json()["code"]
    second = client.post(f"{API}/sites/{site}/pairing-code", headers=ana.h).json()["code"]
    with get_session_factory()() as db:
        hashes = set(db.scalars(select(PairingCode.code_hash)))
    assert hashes == {keyed_hash(second)}
    assert first is not None


def test_viewers_cannot_make_pairing_codes(client, ana, jun):
    circle = circle_with(client, ana, (jun, "viewer"))
    site = make_site(client, ana, circle).json()["id"]
    assert client.post(f"{API}/sites/{site}/pairing-code", headers=jun.h).status_code == 403


# ---------------------------------------------------------------- isolation


def test_another_circles_sites_look_like_they_do_not_exist(client, ana, eve):
    circle = circle_with(client, ana)
    site = make_site(client, ana, circle).json()["id"]
    circle_with(client, eve)
    made_up = "00000000-0000-4000-8000-000000000000"
    site_routes = [
        ("get", f"/sites/{site}", None),
        ("patch", f"/sites/{site}", {"name": "mine now"}),
        ("delete", f"/sites/{site}", None),
        ("get", f"/sites/{site}/summary", None),
        ("post", f"/sites/{site}/pairing-code", None),
    ]
    for method, path, body in site_routes:
        kwargs = {"headers": eve.h, **({"json": body} if body is not None else {})}
        r = getattr(client, method)(f"{API}{path}", **kwargs)
        assert r.status_code == 404 and r.json()["error"]["code"] == "site_not_found", path
        fake = getattr(client, method)(f"{API}{path.replace(site, made_up)}", **kwargs)
        assert fake.json() == r.json()
    for method, body in (("get", None), ("post", {"name": "Sneaky"})):
        kwargs = {"headers": eve.h, **({"json": body} if body else {})}
        r = getattr(client, method)(f"{API}/circles/{circle}/sites", **kwargs)
        assert r.status_code == 404 and r.json()["error"]["code"] == "circle_not_found"
    assert client.get(f"{API}/sites/{site}", headers=ana.h).json()["name"] == "Home"
