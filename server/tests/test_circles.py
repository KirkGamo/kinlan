"""Circles, members and invites, plus isolation between Circles (Sections 4.2, 4.3, 5.3)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import get_session_factory
from app.models import Device, Invite, Site
from app.security import INVITE_ALPHABET

API = "/api/v1"


class Person:
    """A registered user and their auth header."""

    def __init__(self, client, name: str):
        email = f"{name.lower()}@example.com"
        r = client.post(
            f"{API}/auth/register",
            json={"email": email, "password": "long enough password", "display_name": name},
        )
        assert r.status_code == 201, r.text
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        self.id = client.get(f"{API}/me", headers=self.h).json()["id"]
        self.name = name


@pytest.fixture
def ana(client):
    return Person(client, "Ana")


@pytest.fixture
def jun(client):
    return Person(client, "Jun")


@pytest.fixture
def eve(client):
    """Someone in a different Circle entirely."""
    return Person(client, "Eve")


def make_circle(client, who, name="Dela Cruz Home") -> str:
    r = client.post(f"{API}/circles", json={"name": name}, headers=who.h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def invite(client, who, circle, role="viewer") -> str:
    r = client.post(f"{API}/circles/{circle}/invites", json={"role": role}, headers=who.h)
    assert r.status_code == 201, r.text
    return r.json()["code"]


def join(client, who, code):
    return client.post(f"{API}/invites/accept", json={"code": code}, headers=who.h)


def members(client, who, circle) -> dict[str, str]:
    r = client.get(f"{API}/circles/{circle}/members", headers=who.h)
    assert r.status_code == 200, r.text
    return {m["display_name"]: m["role"] for m in r.json()["items"]}


# ---------------------------------------------------------------- create and list


def test_creating_a_circle_makes_you_its_owner(client, ana):
    r = client.post(f"{API}/circles", json={"name": "  Dela Cruz Home  "}, headers=ana.h)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Dela Cruz Home" and body["role"] == "owner"
    assert body["member_count"] == 1 and body["site_count"] == 0
    assert [c["id"] for c in client.get(f"{API}/circles", headers=ana.h).json()["items"]] == [
        body["id"]
    ]


def test_list_shows_only_your_circles_with_your_role_in_each(client, ana, jun):
    home = make_circle(client, ana)
    lab = make_circle(client, jun, "CICT Lab 3")
    join(client, ana, invite(client, jun, lab, "admin"))
    roles = {
        c["name"]: c["role"] for c in client.get(f"{API}/circles", headers=ana.h).json()["items"]
    }
    assert roles == {"Dela Cruz Home": "owner", "CICT Lab 3": "admin"}
    assert [c["id"] for c in client.get(f"{API}/circles", headers=jun.h).json()["items"]] == [lab]
    assert home


def test_circle_needs_a_name(client, ana):
    r = client.post(f"{API}/circles", json={"name": "   "}, headers=ana.h)
    assert r.status_code == 400 and r.json()["error"]["code"] == "validation_error"


# ---------------------------------------------------------------- invites


def test_invite_code_format_avoids_look_alike_characters(client, ana):
    circle = make_circle(client, ana)
    for _ in range(20):
        code = invite(client, ana, circle)
        assert len(code) == 9 and code[4] == "-"
        assert set(code.replace("-", "")) <= set(INVITE_ALPHABET)
        assert not set(code) & set("0O1IL")


def test_joining_with_an_invite_gives_the_chosen_role(client, ana, jun):
    circle = make_circle(client, ana)
    code = invite(client, ana, circle, "admin")
    r = join(client, jun, code.lower().replace("-", " "))  # typed loosely still works
    assert r.status_code == 200 and r.json()["role"] == "admin" and r.json()["member_count"] == 2
    assert members(client, ana, circle) == {"Ana": "owner", "Jun": "admin"}


def test_an_invite_works_only_once(client, ana, jun, eve):
    code = invite(client, ana, make_circle(client, ana))
    assert join(client, jun, code).status_code == 200
    r = join(client, eve, code)
    assert r.status_code == 404 and r.json()["error"]["code"] == "invite_not_found"


def test_an_expired_invite_is_refused(client, ana, jun):
    code = invite(client, ana, make_circle(client, ana))
    with get_session_factory()() as db:
        db.scalar(select(Invite)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    r = join(client, jun, code)
    assert r.status_code == 400 and r.json()["error"]["code"] == "invite_expired"


def test_invites_expire_after_seven_days(client, ana):
    circle = make_circle(client, ana)
    r = client.post(f"{API}/circles/{circle}/invites", json={}, headers=ana.h)
    expires = datetime.fromisoformat(r.json()["expires_at"])
    assert r.json()["role"] == "viewer"
    assert timedelta(days=6, hours=23) < expires - datetime.now(UTC) <= timedelta(days=7)


def test_joining_a_circle_you_are_in_is_a_conflict_and_keeps_the_code(client, ana, jun):
    circle = make_circle(client, ana)
    join(client, jun, invite(client, ana, circle))
    code = invite(client, ana, circle)
    r = join(client, jun, code)
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_member"
    with get_session_factory()() as db:
        assert db.scalar(select(Invite).where(Invite.used_at.is_(None))) is not None


def test_only_owners_can_invite(client, ana, jun):
    circle = make_circle(client, ana)
    join(client, jun, invite(client, ana, circle, "admin"))
    r = client.post(f"{API}/circles/{circle}/invites", json={"role": "viewer"}, headers=jun.h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


# ---------------------------------------------------------------- roles, leaving, removing


def test_owner_changes_a_role(client, ana, jun):
    circle = make_circle(client, ana)
    join(client, jun, invite(client, ana, circle))
    r = client.patch(
        f"{API}/circles/{circle}/members/{jun.id}", json={"role": "admin"}, headers=ana.h
    )
    assert r.status_code == 200 and r.json()["role"] == "admin"


def test_admins_cannot_change_roles(client, ana, jun):
    circle = make_circle(client, ana)
    join(client, jun, invite(client, ana, circle, "admin"))
    r = client.patch(
        f"{API}/circles/{circle}/members/{ana.id}", json={"role": "viewer"}, headers=jun.h
    )
    assert r.status_code == 403


def test_the_last_owner_cannot_be_demoted_or_leave(client, ana):
    circle = make_circle(client, ana)
    demote = client.patch(
        f"{API}/circles/{circle}/members/{ana.id}", json={"role": "admin"}, headers=ana.h
    )
    leave = client.delete(f"{API}/circles/{circle}/members/{ana.id}", headers=ana.h)
    assert demote.status_code == leave.status_code == 409
    assert demote.json()["error"]["code"] == "last_owner"


def test_an_owner_can_step_down_once_another_owner_exists(client, ana, jun):
    circle = make_circle(client, ana)
    join(client, jun, invite(client, ana, circle, "owner"))
    r = client.patch(
        f"{API}/circles/{circle}/members/{ana.id}", json={"role": "viewer"}, headers=ana.h
    )
    assert r.status_code == 200
    assert members(client, jun, circle) == {"Jun": "owner", "Ana": "viewer"}


def test_anyone_can_leave(client, ana, jun):
    circle = make_circle(client, ana)
    join(client, jun, invite(client, ana, circle))
    assert (
        client.delete(f"{API}/circles/{circle}/members/{jun.id}", headers=jun.h).status_code == 204
    )
    assert members(client, ana, circle) == {"Ana": "owner"}


def test_only_owners_remove_other_people(client, ana, jun, eve):
    circle = make_circle(client, ana)
    join(client, jun, invite(client, ana, circle, "admin"))
    join(client, eve, invite(client, ana, circle))
    assert (
        client.delete(f"{API}/circles/{circle}/members/{eve.id}", headers=jun.h).status_code == 403
    )
    assert (
        client.delete(f"{API}/circles/{circle}/members/{eve.id}", headers=ana.h).status_code == 204
    )


def test_leaving_makes_your_devices_shared(client, ana, jun):
    circle = make_circle(client, ana)
    join(client, jun, invite(client, ana, circle))
    with get_session_factory()() as db:
        site = Site(circle_id=circle, name="Home")
        db.add(site)
        db.flush()
        db.add(Device(site_id=site.id, mac="a8:9c:ed:00:00:01", owner_user_id=jun.id))
        db.commit()
    client.delete(f"{API}/circles/{circle}/members/{jun.id}", headers=jun.h)
    with get_session_factory()() as db:
        assert db.scalar(select(Device)).owner_user_id is None


def test_owner_deletes_the_circle_and_its_sites(client, ana, jun):
    circle = make_circle(client, ana)
    join(client, jun, invite(client, ana, circle, "admin"))
    with get_session_factory()() as db:
        db.add(Site(circle_id=circle, name="Home"))
        db.commit()
    assert client.delete(f"{API}/circles/{circle}", headers=jun.h).status_code == 403
    assert client.delete(f"{API}/circles/{circle}", headers=ana.h).status_code == 204
    assert client.get(f"{API}/circles", headers=jun.h).json()["items"] == []
    with get_session_factory()() as db:
        assert db.scalar(select(Site)) is None


# ---------------------------------------------------------------- isolation between Circles


def test_another_circle_looks_like_it_does_not_exist(client, ana, eve):
    """Every Circle route answers 404 to an outsider, the same as for a made-up id."""
    circle = make_circle(client, ana)
    make_circle(client, eve, "Eve's place")
    attempts = [
        ("get", f"/circles/{circle}/members", None),
        ("post", f"/circles/{circle}/invites", {"role": "owner"}),
        ("patch", f"/circles/{circle}/members/{ana.id}", {"role": "viewer"}),
        ("delete", f"/circles/{circle}/members/{ana.id}", None),
        ("delete", f"/circles/{circle}", None),
    ]
    made_up = "00000000-0000-4000-8000-000000000000"
    for method, path, body in attempts:
        kwargs = {"headers": eve.h, **({"json": body} if body is not None else {})}
        r = getattr(client, method)(f"{API}{path}", **kwargs)
        assert r.status_code == 404, (method, path, r.status_code)
        assert r.json()["error"]["code"] == "circle_not_found"
        fake = getattr(client, method)(f"{API}{path.replace(circle, made_up)}", **kwargs)
        assert fake.json() == r.json()
    assert members(client, ana, circle) == {"Ana": "owner"}


def test_circle_routes_require_sign_in(client, ana):
    circle = make_circle(client, ana)
    assert client.get(f"{API}/circles").status_code == 401
    assert client.get(f"{API}/circles/{circle}/members").status_code == 401
    assert client.post(f"{API}/invites/accept", json={"code": "ABCD-EFGH"}).status_code == 401
