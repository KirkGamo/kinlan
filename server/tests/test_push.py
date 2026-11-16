"""Push tokens, each member's push switches, and Expo push delivery (#54; plan, Section 4.4)."""

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select

from app import push
from app.db import get_session_factory
from app.models import Alert, PushTicket, PushToken

API = "/api/v1"
TOKEN_A = "ExponentPushToken[ana-phone-aaaaaaaaaaaa]"
TOKEN_J = "ExponentPushToken[jun-phone-jjjjjjjjjjjj]"
TOKEN_E = "ExponentPushToken[eve-phone-eeeeeeeeeeee]"


def join(client, owner, circle_id, person, role="viewer"):
    code = client.post(
        f"{API}/circles/{circle_id}/invites", json={"role": role}, headers=owner.h
    ).json()["code"]
    assert client.post(f"{API}/invites/accept", json={"code": code}, headers=person.h).is_success


def register(client, who, token):
    r = client.post(f"{API}/push-tokens", json={"token": token}, headers=who.h)
    assert r.status_code == 200, r.text


def add_alert(site_id, type_="new_device", severity="warning", ago=timedelta(0), ref=None):
    with get_session_factory()() as db:
        alert = Alert(
            site_id=site_id,
            type=type_,
            severity=severity,
            title="Someone new joined: Galaxy-A15",
            body="Whose is it?",
            subject_ref=ref,
            created_at=datetime.now(UTC) - ago,
        )
        db.add(alert)
        db.commit()
        return alert.id


class FakeExpo:
    """Records what would be sent and answers like Expo."""

    def __init__(self, tickets=None, fail=False):
        self.sent: list[dict] = []
        self.tickets = tickets or {}
        self.fail = fail

    def __call__(self, messages):
        if self.fail:
            raise httpx.ConnectError("no network")
        self.sent.extend(messages)
        return [
            self.tickets.get(m["to"], {"status": "ok", "id": f"ticket-{m['to'][-6:-1]}"})
            for m in messages
        ]


def run_dispatch(fake):
    with get_session_factory()() as db:
        return push.dispatch(db, sender=fake)


# ---------------------------------------------------------------- tokens


def test_a_phone_registers_and_moves_to_whoever_signs_in(client, ana, jun):
    register(client, ana, TOKEN_A)
    register(client, jun, TOKEN_A)  # Jun signs in on the same phone
    with get_session_factory()() as db:
        assert db.get(PushToken, TOKEN_A).user_id.hex == jun.id.replace("-", "")


def test_only_expo_tokens_are_accepted(client, ana):
    r = client.post(f"{API}/push-tokens", json={"token": "not-a-token"}, headers=ana.h)
    assert r.status_code == 400 and r.json()["error"]["code"] == "validation_error"


def test_signing_out_removes_only_your_own_token(client, ana, eve):
    register(client, ana, TOKEN_A)
    assert client.delete(f"{API}/push-tokens/{TOKEN_A}", headers=eve.h).status_code == 204
    with get_session_factory()() as db:
        assert db.get(PushToken, TOKEN_A) is not None
    assert client.delete(f"{API}/push-tokens/{TOKEN_A}", headers=ana.h).status_code == 204
    with get_session_factory()() as db:
        assert db.get(PushToken, TOKEN_A) is None


# ---------------------------------------------------------------- switches


def test_switches_default_to_the_brief_and_belong_to_each_member(client, ana, jun, eve, home):
    circle = home["circle_id"]
    join(client, ana, circle, jun)
    url = f"{API}/circles/{circle}/notifications"
    assert client.get(url, headers=jun.h).json() == {
        "outages": True,
        "new_devices": True,
        "security": True,
        "performance": False,
    }
    r = client.patch(url, json={"new_devices": False, "performance": True}, headers=jun.h)
    assert r.json()["new_devices"] is False and r.json()["performance"] is True
    assert client.get(url, headers=ana.h).json()["new_devices"] is True  # Ana's are unchanged
    assert client.get(url, headers=eve.h).status_code == 404  # outsiders see nothing


# ---------------------------------------------------------------- delivery


def test_an_alert_reaches_members_who_want_it_and_nobody_else(client, ana, jun, eve, home):
    join(client, ana, home["circle_id"], jun)
    other = client.post(f"{API}/circles", json={"name": "Eve's"}, headers=eve.h).json()
    assert other["id"] != home["circle_id"]
    register(client, ana, TOKEN_A)
    register(client, jun, TOKEN_J)
    register(client, eve, TOKEN_E)  # in another Circle
    client.patch(
        f"{API}/circles/{home['circle_id']}/notifications",
        json={"new_devices": False},
        headers=jun.h,
    )
    alert_id = add_alert(home["id"], ref="2b6c9a54-0000-0000-0000-000000000000")
    fake = FakeExpo()
    assert run_dispatch(fake) == 1
    assert [m["to"] for m in fake.sent] == [TOKEN_A]
    msg = fake.sent[0]
    assert msg["data"]["url"] == "/devices?device=2b6c9a54-0000-0000-0000-000000000000"
    assert msg["channelId"] == "warning" and msg["title"].startswith("Someone new joined")
    with get_session_factory()() as db:
        assert db.get(Alert, alert_id).pushed_at is not None
        assert db.scalars(select(PushTicket.token)).all() == [TOKEN_A]
    assert run_dispatch(FakeExpo()) == 0  # pushed once only


def test_slow_internet_stays_in_the_app_unless_switched_on(client, ana, home):
    register(client, ana, TOKEN_A)
    add_alert(home["id"], type_="high_latency")
    fake = FakeExpo()
    run_dispatch(fake)
    assert fake.sent == []
    client.patch(
        f"{API}/circles/{home['circle_id']}/notifications",
        json={"performance": True},
        headers=ana.h,
    )
    add_alert(home["id"], type_="packet_loss")
    run_dispatch(fake)
    assert [m["data"]["url"] for m in fake.sent] == ["/alerts"]


def test_an_outage_links_to_the_failing_light_and_recovery_to_alerts(client, ana, home):
    register(client, ana, TOKEN_A)
    down = add_alert(home["id"], type_="unreachable", severity="critical")
    fake = FakeExpo()
    run_dispatch(fake)
    add_alert(home["id"], type_="back_online", severity="info")
    back = FakeExpo(tickets={TOKEN_A: {"status": "ok", "id": "ticket-back"}})
    run_dispatch(back)
    assert [m["data"]["url"] for m in back.sent] == ["/alerts"]
    assert fake.sent[0]["data"]["url"] == f"/?light=failing&at={down}"
    assert fake.sent[0]["data"]["siteId"] == str(home["id"])


def test_old_alerts_are_never_pushed_and_failures_retry(client, ana, home):
    register(client, ana, TOKEN_A)
    stale = add_alert(home["id"], type_="unreachable", severity="critical", ago=timedelta(hours=1))
    fresh = add_alert(home["id"], type_="unreachable", severity="critical")
    assert run_dispatch(FakeExpo(fail=True)) == 0  # Expo down: nothing marked as pushed
    with get_session_factory()() as db:
        assert db.get(Alert, fresh).pushed_at is None
    fake = FakeExpo()
    assert run_dispatch(fake) == 1
    assert fake.sent[0]["priority"] == "high"
    with get_session_factory()() as db:
        assert db.get(Alert, stale).pushed_at is not None  # marked, never sent


def test_dead_tokens_are_removed_at_once_or_from_receipts(client, ana, jun, home):
    join(client, ana, home["circle_id"], jun)
    register(client, ana, TOKEN_A)
    register(client, jun, TOKEN_J)
    gone = {"status": "error", "details": {"error": "DeviceNotRegistered"}}
    add_alert(home["id"])
    run_dispatch(FakeExpo(tickets={TOKEN_J: gone}))
    with get_session_factory()() as db:
        assert db.get(PushToken, TOKEN_J) is None  # rejected immediately
        ticket = db.scalars(select(PushTicket)).one()
        ticket.created_at = datetime.now(UTC) - timedelta(minutes=20)
        db.commit()
        ticket_id = ticket.ticket_id
        result = push.check_receipts(db, fetcher=lambda ids: {ticket_id: gone})
    assert result == {"checked": 1, "tokens_removed": 1}
    with get_session_factory()() as db:
        assert db.get(PushToken, TOKEN_A) is None
        assert db.scalars(select(PushTicket)).all() == []
