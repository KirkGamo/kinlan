"""Agent-side helpers and fixtures shared by the agent API and alert tests."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

API = "/api/v1"


def iso(dt: datetime) -> str:
    return dt.isoformat()


@pytest.fixture
def home(client, ana):
    """Ana's Circle with one site, Home."""
    circle = client.post(f"{API}/circles", json={"name": "Dela Cruz Home"}, headers=ana.h).json()
    return client.post(
        f"{API}/circles/{circle['id']}/sites", json={"name": "Home"}, headers=ana.h
    ).json()


def pair(client, owner, site_id, **extra) -> dict:
    code = client.post(f"{API}/sites/{site_id}/pairing-code", headers=owner.h).json()["code"]
    body = {
        "code": code,
        "hostname": "DESKTOP-01",
        "os": "Windows 11",
        "agent_version": "0.1.0",
        "network_cidr": "192.168.1.0/24",
        **extra,
    }
    r = client.post(f"{API}/agent/pair", json=body)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def agent(client, ana, home):
    paired = pair(client, ana, home["id"])
    return {"h": {"Authorization": f"Bearer {paired['agent_token']}"}, "owner_h": ana.h, **paired}


def batch(**parts) -> dict:
    now = datetime.now(UTC)
    return {"batch_id": str(uuid.uuid4()), "agent_version": "0.1.0", "sent_at": iso(now), **parts}


def sample(minutes_ago=0.0, target="internet", rtt=20.0, ok=True, ip="8.8.8.8") -> dict:
    ts = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    return {"ts": iso(ts), "target": target, "ip": ip, "rtt_ms": rtt if ok else None, "ok": ok}


def scan(*devices) -> list[dict]:
    return [{"mac": m, "ip": ip, "hostname": h, "vendor": v} for m, ip, h, v in devices]


ROUTER = ("64:f8:8a:00:00:01", "192.168.1.1", None, "China Mobile IOT")
PC = ("50:84:92:00:00:02", "192.168.1.13", "DESKTOP-01", "Intel")
PHONE = ("a8:9c:ed:00:00:03", "192.168.1.31", "Galaxy-A15", "Samsung")
