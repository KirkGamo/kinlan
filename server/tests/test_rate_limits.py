"""Rate limits and the ingest size cap (technical plan, Section 7; issue #93). Limits are off in
the test environment; each test here switches them on with fresh counters."""

import gzip
import json

import pytest

from app.ratelimit import limiter
from tests.agent_fixtures import batch, pair, sample

API = "/api/v1"


@pytest.fixture
def limits_on():
    """Listed last in a test's arguments, so sign-ups and pairing in other fixtures don't count."""
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


def assert_rate_limited(r):
    assert r.status_code == 429, r.text
    message = "Too many requests. Wait a minute and try again."
    assert r.json() == {"error": {"code": "rate_limited", "message": message}}
    assert r.headers["retry-after"] == "60"


def test_ingest_allows_30_batches_a_minute_per_agent(client, ana, home, agent, limits_on):
    for _ in range(30):
        r = client.post(f"{API}/agent/ingest", json=batch(samples=[sample(0)]), headers=agent["h"])
        assert r.status_code == 200, r.text
    assert_rate_limited(
        client.post(f"{API}/agent/ingest", json=batch(samples=[sample(0)]), headers=agent["h"])
    )


def test_the_ingest_limit_is_per_agent_not_per_ip(client, ana, home, agent, limits_on):
    """Every agent in these tests shares the test client's address."""
    office = client.post(f"{API}/circles", json={"name": "Office"}, headers=ana.h).json()
    lab = client.post(f"{API}/circles/{office['id']}/sites", json={"name": "Lab"}, headers=ana.h)
    other = {"Authorization": f"Bearer {pair(client, ana, lab.json()['id'])['agent_token']}"}
    for _ in range(30):
        client.post(f"{API}/agent/ingest", json=batch(samples=[sample(0)]), headers=agent["h"])
    r = client.post(f"{API}/agent/ingest", json=batch(samples=[sample(0)]), headers=other)
    assert r.status_code == 200, r.text


def test_people_get_120_requests_a_minute_on_other_routes(client, ana, jun, limits_on):
    for _ in range(120):
        assert client.get(f"{API}/me", headers=ana.h).status_code == 200
    assert_rate_limited(client.get(f"{API}/me", headers=ana.h))
    # Counted per person, not per address: Jun, on the same address, is unaffected.
    assert client.get(f"{API}/me", headers=jun.h).status_code == 200


def test_a_429_still_carries_cors_headers_for_the_web_app(client, ana, limits_on):
    origin = {"Origin": "http://localhost:8081"}
    for _ in range(120):
        client.get(f"{API}/me", headers={**ana.h, **origin})
    r = client.get(f"{API}/me", headers={**ana.h, **origin})
    assert r.status_code == 429
    assert r.headers["access-control-allow-origin"] == "http://localhost:8081"


def test_the_health_check_is_never_limited(client, limits_on):
    for _ in range(130):
        assert client.get("/healthz").status_code == 200


def test_ingest_bodies_are_capped_at_1_mb_after_decompression(client, agent, limits_on):
    # 1.1 MB of JSON that gzips to a few KB: the cap applies to what it unpacks to.
    body = batch(samples=[sample(0)], padding="x" * (1100 * 1024))
    raw = gzip.compress(json.dumps(body).encode())
    assert len(raw) < 20 * 1024
    r = client.post(
        f"{API}/agent/ingest",
        content=raw,
        headers={**agent["h"], "Content-Encoding": "gzip", "Content-Type": "application/json"},
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "body_too_large"
