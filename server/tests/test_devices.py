"""Device endpoints: list and filters, detail, edits, trust resolving the alert, ping history,
and isolation between Circles (issue #52)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db import get_session_factory
from app.models import Alert, Device, PingTest
from tests.agent_fixtures import PC, PHONE, ROUTER, batch, scan

API = "/api/v1"


def ingest(client, agent, **parts):
    r = client.post(f"{API}/agent/ingest", json=batch(**parts), headers=agent["h"])
    assert r.status_code == 200, r.text


def seeded(client, agent):
    """Baseline: router and PC. Later: a phone joins (new, needs review)."""
    ingest(client, agent, netinfo={"gateway": "192.168.1.1"}, devices=scan(ROUTER, PC))
    ingest(client, agent, netinfo={"gateway": "192.168.1.1"}, devices=scan(ROUTER, PC, PHONE))
    with get_session_factory()() as db:
        return {d.mac: str(d.id) for d in db.scalars(select(Device))}


def devices(client, who, site_id, query=""):
    r = client.get(f"{API}/sites/{site_id}/devices{query}", headers=who.h)
    assert r.status_code == 200, r.text
    return r.json()["items"]


def join(client, owner, circle_id, person, role):
    code = client.post(
        f"{API}/circles/{circle_id}/invites", json={"role": role}, headers=owner.h
    ).json()["code"]
    assert client.post(f"{API}/invites/accept", json={"code": code}, headers=person.h).is_success


# ---------------------------------------------------------------- list and detail


def test_list_puts_new_devices_first_with_names_and_types(client, ana, agent, home):
    seeded(client, agent)
    items = devices(client, ana, home["id"])
    assert [d["display_name"] for d in items] == ["Galaxy-A15", "China Mobile IOT", "DESKTOP-01"]
    phone = items[0]
    assert phone["needs_review"] and not phone["baseline"] and not phone["trusted"]
    assert phone["device_type"] == "phone" and phone["ip"] == "192.168.1.31"
    router = next(d for d in items if d["mac"] == ROUTER[0])
    assert router["device_type"] == "router" and router["baseline"] and not router["needs_review"]


def test_filters(client, ana, agent, home):
    ids = seeded(client, agent)
    assert [d["mac"] for d in devices(client, ana, home["id"], "?status=review")] == [PHONE[0]]
    with get_session_factory()() as db:
        db.get(Device, ids[PC[0]]).online = False
        db.commit()
    assert [d["mac"] for d in devices(client, ana, home["id"], "?status=offline")] == [PC[0]]
    assert len(devices(client, ana, home["id"], "?status=online")) == 2
    bad = client.get(f"{API}/sites/{home['id']}/devices?status=sideways", headers=ana.h)
    assert bad.status_code == 400


def test_detail_has_risky_ports_and_the_last_ping_test(client, ana, agent, home):
    ids = seeded(client, agent)
    ingest(client, agent, port_findings=[{"mac": ROUTER[0], "port": 23, "service": "telnet"}])
    now = datetime.now(UTC)
    with get_session_factory()() as db:
        for i, avg in enumerate([5.0, 8.0]):
            db.add(
                PingTest(
                    device_id=ids[ROUTER[0]],
                    ts=now - timedelta(minutes=10 - i),
                    sent=10,
                    received=10,
                    loss_pct=0,
                    min_ms=1,
                    avg_ms=avg,
                    max_ms=9,
                    jitter_ms=1,
                )
            )
        db.commit()
    d = client.get(f"{API}/devices/{ids[ROUTER[0]]}", headers=ana.h).json()
    assert d["open_risky_ports"] == 1 and d["risky_ports"][0]["service"] == "telnet"
    assert d["last_ping_test"]["avg_ms"] == 8.0
    assert devices(client, ana, home["id"])[1]["open_risky_ports"] == 1


# ---------------------------------------------------------------- edits


def test_rename_type_owner_and_clear(client, ana, jun, agent, home):
    ids = seeded(client, agent)
    join(client, ana, home["circle_id"], jun, "viewer")
    url = f"{API}/devices/{ids[PHONE[0]]}"
    r = client.patch(
        url,
        json={"custom_name": "  Jun's phone ", "owner_user_id": jun.id, "device_type": "laptop"},
        headers=ana.h,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["display_name"] == "Jun's phone" and d["device_type"] == "laptop"
    assert d["owner"] == {"user_id": jun.id, "display_name": "Jun"}
    mine = devices(client, jun, home["id"], "?owner=me")
    assert [x["id"] for x in mine] == [ids[PHONE[0]]]
    cleared = client.patch(url, json={"custom_name": None, "owner_user_id": None}, headers=ana.h)
    assert cleared.json()["display_name"] == "Galaxy-A15" and cleared.json()["owner"] is None
    untouched = client.patch(url, json={}, headers=ana.h).json()
    assert untouched["device_type"] == "laptop"


def test_owner_must_be_in_the_circle(client, ana, eve, agent):
    ids = seeded(client, agent)
    r = client.patch(f"{API}/devices/{ids[PC[0]]}", json={"owner_user_id": eve.id}, headers=ana.h)
    assert r.status_code == 400 and r.json()["error"]["code"] == "owner_not_member"


def test_trusting_a_new_device_resolves_its_alert(client, ana, agent, home):
    ids = seeded(client, agent)
    with get_session_factory()() as db:
        alert = db.scalar(select(Alert).where(Alert.type == "new_device"))
        assert alert.resolved_at is None and alert.subject_ref == ids[PHONE[0]]
    r = client.patch(f"{API}/devices/{ids[PHONE[0]]}", json={"trusted": True}, headers=ana.h)
    assert r.json()["trusted"] and not r.json()["needs_review"]
    with get_session_factory()() as db:
        assert db.scalar(select(Alert).where(Alert.type == "new_device")).resolved_at is not None
    assert devices(client, ana, home["id"], "?status=review") == []


def test_viewers_read_but_cannot_edit(client, ana, jun, agent, home):
    ids = seeded(client, agent)
    join(client, ana, home["circle_id"], jun, "viewer")
    assert len(devices(client, jun, home["id"])) == 3
    r = client.patch(f"{API}/devices/{ids[PHONE[0]]}", json={"trusted": True}, headers=jun.h)
    assert r.status_code == 403


def test_names_are_limited_to_80_characters(client, ana, agent):
    ids = seeded(client, agent)
    r = client.patch(f"{API}/devices/{ids[PC[0]]}", json={"custom_name": "x" * 81}, headers=ana.h)
    assert r.status_code == 400


# ---------------------------------------------------------------- ping history


def test_ping_history_is_newest_first_with_pages(client, ana, agent):
    ids = seeded(client, agent)
    now = datetime.now(UTC)
    with get_session_factory()() as db:
        for i in range(3):
            db.add(
                PingTest(
                    device_id=ids[PC[0]],
                    ts=now - timedelta(minutes=3 - i),
                    sent=10,
                    received=10 - i,
                    loss_pct=10.0 * i,
                    min_ms=1,
                    avg_ms=2,
                    max_ms=3,
                    jitter_ms=0.5,
                )
            )
        db.commit()
    url = f"{API}/devices/{ids[PC[0]]}/ping-tests"
    first = client.get(f"{url}?limit=2", headers=ana.h).json()
    assert [t["received"] for t in first["items"]] == [8, 9] and first["next_cursor"]
    second = client.get(f"{url}?limit=2&cursor={first['next_cursor']}", headers=ana.h).json()
    assert [t["received"] for t in second["items"]] == [10] and second["next_cursor"] is None


# ---------------------------------------------------------------- isolation


def test_another_circles_devices_look_like_they_do_not_exist(client, ana, eve, agent, home):
    ids = seeded(client, agent)
    client.post(f"{API}/circles", json={"name": "Eve's"}, headers=eve.h)
    device = ids[PHONE[0]]
    made_up = "00000000-0000-4000-8000-000000000000"
    for method, path, body in [
        ("get", f"/devices/{device}", None),
        ("patch", f"/devices/{device}", {"trusted": True}),
        ("get", f"/devices/{device}/ping-tests", None),
    ]:
        kwargs = {"headers": eve.h, **({"json": body} if body is not None else {})}
        r = getattr(client, method)(f"{API}{path}", **kwargs)
        assert r.status_code == 404 and r.json()["error"]["code"] == "device_not_found", path
        fake = getattr(client, method)(f"{API}{path.replace(device, made_up)}", **kwargs)
        assert fake.json() == r.json()
    r = client.get(f"{API}/sites/{home['id']}/devices", headers=eve.h)
    assert r.status_code == 404 and r.json()["error"]["code"] == "site_not_found"
    assert not client.get(f"{API}/devices/{device}", headers=ana.h).json()["trusted"]
