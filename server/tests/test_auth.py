"""Auth: register, login, refresh rotation and reuse detection, logout, /me (Section 4.2)."""

from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session_factory
from app.models import Circle, Membership, RefreshToken, Role, User
from app.security import ALGORITHM, sha256_hex

API = "/api/v1"
ANA = {"email": "Ana.M@Example.com", "password": "correct horse battery", "display_name": "Ana M."}


def register(client, **overrides):
    return client.post(f"{API}/auth/register", json={**ANA, **overrides})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------- register


def test_register_returns_tokens_and_stores_a_hashed_lowercase_email(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 900
    with get_session_factory()() as db:
        user = db.scalar(select(User))
        assert user.email == "ana.m@example.com"
        assert user.password_hash.startswith("$argon2id$")
        assert ANA["password"] not in user.password_hash


def test_register_twice_with_the_same_email_in_any_case_is_a_conflict(client):
    register(client)
    r = register(client, email="ANA.M@EXAMPLE.COM")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


def test_register_rejects_a_short_password_with_the_standard_error_shape(client):
    r = register(client, password="short")
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "validation_error" and err["message"].startswith("password")


# ---------------------------------------------------------------- login and /me


def test_login_then_me(client):
    register(client)
    r = client.post(
        f"{API}/auth/login", json={"email": "ana.m@example.com", "password": ANA["password"]}
    )
    assert r.status_code == 200
    me = client.get(f"{API}/me", headers=bearer(r.json()["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "ana.m@example.com" and me.json()["display_name"] == "Ana M."


def test_wrong_password_and_unknown_email_look_the_same(client):
    register(client)
    wrong = client.post(
        f"{API}/auth/login", json={"email": ANA["email"], "password": "nope-nope-nope"}
    )
    unknown = client.post(
        f"{API}/auth/login", json={"email": "who@example.com", "password": "x" * 12}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_me_requires_a_valid_access_token(client):
    assert client.get(f"{API}/me").json()["error"]["code"] == "not_authenticated"
    assert (
        client.get(f"{API}/me", headers=bearer("not-a-jwt")).json()["error"]["code"]
        == "invalid_token"
    )


def test_an_expired_access_token_is_reported_as_expired(client):
    user_id = client.get(
        f"{API}/me", headers=bearer(register(client).json()["access_token"])
    ).json()["id"]
    past = datetime.now(UTC) - timedelta(hours=1)
    token = jwt.encode(
        {"sub": user_id, "iat": past, "exp": past + timedelta(minutes=15), "type": "access"},
        get_settings().jwt_secret,
        algorithm=ALGORITHM,
    )
    r = client.get(f"{API}/me", headers=bearer(token))
    assert r.status_code == 401 and r.json()["error"]["code"] == "token_expired"


def test_a_refresh_token_is_not_accepted_as_an_access_token(client):
    pair = register(client).json()
    assert client.get(f"{API}/me", headers=bearer(pair["refresh_token"])).status_code == 401


# ---------------------------------------------------------------- refresh rotation


def test_refresh_rotates_the_token_and_links_old_to_new(client):
    first = register(client).json()
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 200
    second = r.json()
    assert second["refresh_token"] != first["refresh_token"]
    with get_session_factory()() as db:
        old = db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == sha256_hex(first["refresh_token"])
            )
        )
        new = db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == sha256_hex(second["refresh_token"])
            )
        )
        assert old.revoked_at is not None and old.replaced_by == new.id and new.revoked_at is None


def test_reusing_an_old_refresh_token_signs_out_every_session(client):
    first = register(client).json()
    other_device = client.post(
        f"{API}/auth/login", json={"email": ANA["email"], "password": ANA["password"]}
    ).json()
    second = client.post(
        f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]}
    ).json()

    reuse = client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert reuse.status_code == 401 and reuse.json()["error"]["code"] == "refresh_token_reused"
    for token in (second["refresh_token"], other_device["refresh_token"]):
        assert client.post(f"{API}/auth/refresh", json={"refresh_token": token}).status_code == 401


def test_an_expired_refresh_token_is_refused(client):
    pair = register(client).json()
    with get_session_factory()() as db:
        row = db.scalar(select(RefreshToken))
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r.status_code == 401 and r.json()["error"]["code"] == "refresh_token_expired"


def test_an_unknown_refresh_token_is_refused(client):
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": "x" * 43})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_refresh_token"


# ---------------------------------------------------------------- logout and delete


def test_logout_revokes_the_refresh_token(client):
    pair = register(client).json()
    assert (
        client.post(f"{API}/auth/logout", json={"refresh_token": pair["refresh_token"]}).status_code
        == 204
    )
    assert (
        client.post(
            f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]}
        ).status_code
        == 401
    )


def test_delete_me_removes_the_account(client):
    token = register(client).json()["access_token"]
    assert client.delete(f"{API}/me", headers=bearer(token)).status_code == 204
    with get_session_factory()() as db:
        assert db.scalar(select(User)) is None and db.scalar(select(RefreshToken)) is None


def test_delete_me_is_refused_for_the_last_owner_of_a_circle(client):
    token = register(client).json()["access_token"]
    with get_session_factory()() as db:
        user = db.scalar(select(User))
        circle = Circle(name="Dela Cruz Home", created_by=user.id)
        db.add(circle)
        db.flush()
        db.add(Membership(circle_id=circle.id, user_id=user.id, role=Role.owner))
        db.commit()
    r = client.delete(f"{API}/me", headers=bearer(token))
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_owner"


def test_delete_me_is_allowed_when_another_owner_remains(client):
    token = register(client).json()["access_token"]
    register(client, email="jun@example.com", display_name="Jun R.")
    with get_session_factory()() as db:
        ana = db.scalar(select(User).where(User.email == "ana.m@example.com"))
        jun = db.scalar(select(User).where(User.email == "jun@example.com"))
        circle = Circle(name="Dela Cruz Home", created_by=ana.id)
        db.add(circle)
        db.flush()
        db.add_all(
            [
                Membership(circle_id=circle.id, user_id=ana.id, role=Role.owner),
                Membership(circle_id=circle.id, user_id=jun.id, role=Role.owner),
            ]
        )
        db.commit()
    assert client.delete(f"{API}/me", headers=bearer(token)).status_code == 204


def test_unknown_routes_use_the_standard_error_shape(client):
    r = client.get(f"{API}/nothing-here")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
