"""The per-site summary cache: served from memory between writes, cleared by every committed
write (ORM or Core), still checks the caller's role, and computes once for concurrent misses."""

import threading
import time
import uuid

import pytest

from app import summary_cache
from app.routers import sites
from tests.agent_fixtures import PC, PHONE, ROUTER, batch, sample, scan

API = "/api/v1"


@pytest.fixture
def computed(monkeypatch):
    """Count how often the summary is actually computed."""
    calls = []
    real = sites._summary

    def counting(db, site):
        calls.append(site.id)
        return real(db, site)

    monkeypatch.setattr(sites, "_summary", counting)
    return calls


def summary(client, who, site_id):
    r = client.get(f"{API}/sites/{site_id}/summary", headers=who.h)
    assert r.status_code == 200, r.text
    return r.json()


def ingest(client, agent, **parts):
    r = client.post(f"{API}/agent/ingest", json=batch(**parts), headers=agent["h"])
    assert r.status_code == 200, r.text


def test_repeat_reads_are_served_from_the_cache(client, ana, home, computed):
    first = summary(client, ana, home["id"])
    assert summary(client, ana, home["id"]) == first
    assert len(computed) == 1


def test_an_ingest_shows_at_once(client, ana, agent, home, computed):
    # Agent ingest writes with Core inserts and updates, not ORM objects.
    assert summary(client, ana, home["id"])["gateway"] is None
    ingest(client, agent, samples=[sample(0, target="gateway", rtt=3, ip="192.168.1.1")])
    s = summary(client, ana, home["id"])
    assert s["gateway"]["rtt_ms"] == 3 and s["status"] == "online"
    assert len(computed) == 2


def test_trusting_a_device_shows_at_once(client, ana, agent, home):
    ingest(client, agent, devices=scan(ROUTER, PC))
    ingest(client, agent, devices=scan(ROUTER, PC, PHONE))
    assert summary(client, ana, home["id"])["needs_review"] == 1
    phone = next(
        d
        for d in client.get(f"{API}/sites/{home['id']}/devices", headers=ana.h).json()["items"]
        if d["mac"] == PHONE[0]
    )
    r = client.patch(f"{API}/devices/{phone['id']}", json={"trusted": True}, headers=ana.h)
    assert r.status_code == 200, r.text
    assert summary(client, ana, home["id"])["needs_review"] == 0


def test_the_role_check_runs_on_a_cached_summary(client, ana, eve, home):
    summary(client, ana, home["id"])  # now cached
    r = client.get(f"{API}/sites/{home['id']}/summary", headers=eve.h)
    assert r.status_code == 404


def test_entries_expire(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(summary_cache, "_clock", lambda: now[0])
    site = uuid.uuid4()
    assert summary_cache.get_or_compute(site, lambda: b"one") == b"one"
    now[0] += summary_cache.TTL_S - 0.1
    assert summary_cache.get_or_compute(site, lambda: b"two") == b"one"
    now[0] += 0.2
    assert summary_cache.get_or_compute(site, lambda: b"two") == b"two"


def test_a_summary_computed_across_a_write_is_not_kept():
    site = uuid.uuid4()

    def racing():
        summary_cache.clear()  # a write commits while this summary is being computed
        return b"stale"

    assert summary_cache.get_or_compute(site, racing) == b"stale"
    assert summary_cache.get_or_compute(site, lambda: b"fresh") == b"fresh"


def test_concurrent_misses_compute_once():
    site = uuid.uuid4()
    calls = []

    def slow():
        calls.append(1)
        time.sleep(0.2)
        return b"body"

    results = []
    threads = [
        threading.Thread(target=lambda: results.append(summary_cache.get_or_compute(site, slow)))
        for _ in range(10)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [b"body"] * 10 and len(calls) == 1
