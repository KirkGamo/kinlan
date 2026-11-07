"""The agent API: pairing, ingest (resend-safe, gzip, heartbeat), commands and results, and
isolation between sites (Sections 1.1, 1.2, 3.6, 4.3)."""

import gzip
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.db import get_session_factory
from app.device_types import infer_type
from app.models import (
    Agent,
    Command,
    Device,
    DeviceType,
    Outage,
    PingSample,
    PingTest,
    PortFinding,
    Site,
)

API = "/api/v1"

from tests.agent_fixtures import PC, PHONE, ROUTER, batch, iso, pair, sample, scan  # noqa: E402

# ---------------------------------------------------------------- pairing


def test_pairing_returns_a_token_stored_only_as_a_hash(client, ana, home):
    paired = pair(client, ana, home["id"])
    assert paired["site_id"] == home["id"] and paired["site_name"] == "Home"
    assert len(paired["agent_token"]) >= 43
    with get_session_factory()() as db:
        row = db.get(Agent, paired["agent_id"])
        assert paired["agent_token"] not in row.token_hash and row.hostname == "DESKTOP-01"
        assert db.get(Site, home["id"]).cidr == "192.168.1.0/24"


def test_a_pairing_code_works_once(client, ana, home):
    code = client.post(f"{API}/sites/{home['id']}/pairing-code", headers=ana.h).json()["code"]
    body = {"code": code, "hostname": "PC", "os": "Windows 11", "agent_version": "0.1.0"}
    assert client.post(f"{API}/agent/pair", json=body).status_code == 200
    r = client.post(f"{API}/agent/pair", json=body)
    assert r.status_code == 404 and r.json()["error"]["code"] == "pairing_code_invalid"


def test_re_pairing_replaces_the_old_agent(client, ana, home):
    old = pair(client, ana, home["id"])
    pair(client, ana, home["id"], hostname="NEW-PC")
    r = client.post(
        f"{API}/agent/ingest",
        json=batch(),
        headers={"Authorization": f"Bearer {old['agent_token']}"},
    )
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_agent_token"


def test_old_agents_must_upgrade(client, ana, home):
    code = client.post(f"{API}/sites/{home['id']}/pairing-code", headers=ana.h).json()["code"]
    body = {"code": code, "hostname": "PC", "os": "Windows 11", "agent_version": "0.0.9"}
    r = client.post(f"{API}/agent/pair", json=body)
    assert r.status_code == 426 and r.json()["error"]["code"] == "agent_too_old"


# ---------------------------------------------------------------- ingest


def test_ingest_stores_samples_and_counts_as_a_heartbeat(client, agent, home):
    body = batch(
        netinfo={"local_ip": "192.168.1.13", "cidr": "192.168.1.0/24", "gateway": "192.168.1.1"},
        samples=[
            sample(1),
            sample(0.5, ok=False),
            sample(0, target="gateway", rtt=2, ip="192.168.1.1"),
        ],
    )
    r = client.post(f"{API}/agent/ingest", json=body, headers=agent["h"])
    assert r.status_code == 200 and r.json()["status"] == "stored" and r.json()["samples"] == 3
    with get_session_factory()() as db:
        site = db.get(Site, home["id"])
        assert site.status.value == "online" and site.last_seen_at is not None
        assert str(site.gateway_ip) == "192.168.1.1"
        lost = db.scalar(select(PingSample).where(PingSample.ok.is_(False)))
        assert lost.rtt_ms is None


def test_a_resent_batch_is_stored_once(client, agent):
    body = batch(samples=[sample(1), sample(0)])
    first = client.post(f"{API}/agent/ingest", json=body, headers=agent["h"])
    again = client.post(f"{API}/agent/ingest", json=body, headers=agent["h"])
    assert first.json()["status"] == "stored" and again.json()["status"] == "duplicate"
    assert again.status_code == 200
    with get_session_factory()() as db:
        assert db.scalar(select(func.count()).select_from(PingSample)) == 2


def test_gzip_bodies_are_accepted(client, agent):
    raw = gzip.compress(json.dumps(batch(samples=[sample(0)])).encode())
    r = client.post(
        f"{API}/agent/ingest",
        content=raw,
        headers={**agent["h"], "Content-Encoding": "gzip", "Content-Type": "application/json"},
    )
    assert r.status_code == 200 and r.json()["samples"] == 1


def test_samples_from_the_future_are_dropped_not_the_batch(client, agent):
    future = sample()
    future["ts"] = iso(datetime.now(UTC) + timedelta(minutes=10))
    r = client.post(
        f"{API}/agent/ingest", json=batch(samples=[sample(0), future]), headers=agent["h"]
    )
    assert r.json()["samples"] == 1 and r.json()["rejected_samples"] == 1


def test_first_scan_is_the_baseline_and_later_strangers_are_new(client, agent, home):
    first = client.post(
        f"{API}/agent/ingest",
        headers=agent["h"],
        json=batch(netinfo={"gateway": "192.168.1.1"}, devices=scan(ROUTER, PC)),
    )
    assert first.json()["devices"] == 2 and first.json()["new_devices"] == 0
    second = client.post(
        f"{API}/agent/ingest",
        headers=agent["h"],
        json=batch(netinfo={"gateway": "192.168.1.1"}, devices=scan(ROUTER, PC, PHONE)),
    )
    assert second.json()["new_devices"] == 1
    with get_session_factory()() as db:
        devices = {d.mac: d for d in db.scalars(select(Device))}
    assert devices[ROUTER[0]].baseline and devices[ROUTER[0]].device_type == DeviceType.router
    assert devices[PC[0]].device_type == DeviceType.computer
    assert not devices[PHONE[0]].baseline and devices[PHONE[0]].device_type == DeviceType.phone
    summary = client.get(f"{API}/sites/{home['id']}/summary", headers=agent["owner_h"]).json()
    assert summary["needs_review"] == 1 and summary["devices_total"] == 3


def test_devices_missing_from_scans_for_eleven_minutes_go_offline(client, agent):
    client.post(f"{API}/agent/ingest", headers=agent["h"], json=batch(devices=scan(ROUTER, PHONE)))
    with get_session_factory()() as db:
        phone = db.scalar(select(Device).where(Device.mac == PHONE[0]))
        phone.last_seen_at = datetime.now(UTC) - timedelta(minutes=12)
        db.commit()
    client.post(f"{API}/agent/ingest", headers=agent["h"], json=batch(devices=scan(ROUTER)))
    with get_session_factory()() as db:
        online = {d.mac: d.online for d in db.scalars(select(Device))}
    assert online == {ROUTER[0]: True, PHONE[0]: False}


def test_outages_from_the_buffer_are_stored_once_and_closed(client, agent):
    start = datetime.now(UTC) - timedelta(minutes=30)
    open_one = {"started_at": iso(start), "ended_at": None, "cause": "isp"}
    closed = {**open_one, "ended_at": iso(start + timedelta(minutes=4, seconds=12))}
    client.post(f"{API}/agent/ingest", headers=agent["h"], json=batch(outages=[open_one]))
    client.post(f"{API}/agent/ingest", headers=agent["h"], json=batch(outages=[closed]))
    client.post(f"{API}/agent/ingest", headers=agent["h"], json=batch(outages=[closed]))
    with get_session_factory()() as db:
        rows = list(db.scalars(select(Outage)))
    assert len(rows) == 1 and rows[0].ended_at is not None and rows[0].cause.value == "isp"


def test_port_findings_attach_to_known_devices(client, agent):
    client.post(f"{API}/agent/ingest", headers=agent["h"], json=batch(devices=scan(ROUTER)))
    finding = {"mac": ROUTER[0].upper(), "port": 23, "service": "telnet"}
    unknown = {"mac": "00:11:22:33:44:55", "port": 21, "service": "ftp"}
    for _ in range(2):
        r = client.post(
            f"{API}/agent/ingest", headers=agent["h"], json=batch(port_findings=[finding, unknown])
        )
        assert r.json()["port_findings"] == 1
    with get_session_factory()() as db:
        assert db.scalar(select(func.count()).select_from(PortFinding)) == 1


def test_ingest_validates_the_payload(client, agent):
    r = client.post(
        f"{API}/agent/ingest", headers=agent["h"], json=batch(devices=[{"mac": "not-a-mac"}])
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "validation_error"


def test_agent_routes_need_a_token(client):
    assert client.post(f"{API}/agent/ingest", json=batch()).status_code == 401
    assert client.get(f"{API}/agent/commands?wait=0").status_code == 401


# ---------------------------------------------------------------- commands


def test_a_diagnose_command_round_trip(client, ana, agent, home):
    sent = client.post(
        f"{API}/sites/{home['id']}/commands", json={"type": "diagnose"}, headers=ana.h
    )
    assert sent.status_code == 201 and sent.json()["status"] == "pending"
    polled = client.get(f"{API}/agent/commands?wait=0", headers=agent["h"]).json()["commands"]
    assert [c["id"] for c in polled] == [sent.json()["id"]] and polled[0]["status"] == "running"
    assert client.get(f"{API}/agent/commands?wait=0", headers=agent["h"]).json()["commands"] == []
    result = {
        "steps": [{"n": 4, "name": "Internet answers ping", "status": "fail"}],
        "root_cause_step": 4,
    }
    r = client.post(
        f"{API}/agent/commands/{sent.json()['id']}/result",
        json={"ok": True, "result": result},
        headers=agent["h"],
    )
    assert r.status_code == 200 and r.json()["status"] == "done"
    read = client.get(f"{API}/commands/{sent.json()['id']}", headers=ana.h).json()
    assert read["status"] == "done" and read["result"]["root_cause_step"] == 4


def test_a_ping_test_result_is_kept_in_the_device_history(client, ana, agent, home):
    client.post(f"{API}/agent/ingest", headers=agent["h"], json=batch(devices=scan(PHONE)))
    with get_session_factory()() as db:
        device_id = str(db.scalar(select(Device.id)))
    cmd = client.post(
        f"{API}/sites/{home['id']}/commands",
        headers=ana.h,
        json={"type": "ping_test", "params": {"device_id": device_id}},
    ).json()
    assert cmd["params"] == {"device_id": device_id, "ip": PHONE[1], "mac": PHONE[0], "count": 10}
    client.get(f"{API}/agent/commands?wait=0", headers=agent["h"])
    stats = {
        "sent": 10,
        "received": 9,
        "loss_pct": 10.0,
        "min_ms": 3.1,
        "avg_ms": 8.4,
        "max_ms": 22.0,
        "jitter_ms": 4.2,
    }
    client.post(
        f"{API}/agent/commands/{cmd['id']}/result",
        json={"ok": True, "result": stats},
        headers=agent["h"],
    )
    with get_session_factory()() as db:
        test = db.scalar(select(PingTest))
    assert (test.sent, test.received, test.avg_ms) == (10, 9, 8.4)


def test_ping_tests_need_a_device_on_this_site(client, ana, agent, home):
    missing = client.post(
        f"{API}/sites/{home['id']}/commands",
        headers=ana.h,
        json={"type": "ping_test", "params": {}},
    )
    other = client.post(
        f"{API}/sites/{home['id']}/commands",
        headers=ana.h,
        json={"type": "ping_test", "params": {"device_id": str(uuid.uuid4())}},
    )
    assert missing.status_code == 400 and other.status_code == 404


def test_viewers_cannot_send_commands_but_can_read_them(client, ana, jun, home):
    code = client.post(
        f"{API}/circles/{home['circle_id']}/invites", json={"role": "viewer"}, headers=ana.h
    ).json()["code"]
    client.post(f"{API}/invites/accept", json={"code": code}, headers=jun.h)
    assert (
        client.post(
            f"{API}/sites/{home['id']}/commands", json={"type": "scan"}, headers=jun.h
        ).status_code
        == 403
    )
    cmd = client.post(f"{API}/sites/{home['id']}/commands", json={"type": "scan"}, headers=ana.h)
    assert client.get(f"{API}/commands/{cmd.json()['id']}", headers=jun.h).status_code == 200


def test_unclaimed_commands_expire_after_two_minutes(client, ana, home):
    cmd = client.post(f"{API}/sites/{home['id']}/commands", json={"type": "scan"}, headers=ana.h)
    with get_session_factory()() as db:
        db.get(Command, cmd.json()["id"]).created_at = datetime.now(UTC) - timedelta(minutes=3)
        db.commit()
    read = client.get(f"{API}/commands/{cmd.json()['id']}", headers=ana.h).json()
    assert read["status"] == "expired" and "Is the PC on?" in read["result"]["error"]


def test_a_failed_command_keeps_the_agents_reason(client, ana, agent, home):
    cmd = client.post(
        f"{API}/sites/{home['id']}/commands", json={"type": "port_check"}, headers=ana.h
    )
    client.get(f"{API}/agent/commands?wait=0", headers=agent["h"])
    r = client.post(
        f"{API}/agent/commands/{cmd.json()['id']}/result",
        json={"ok": False, "error": "Npcap is not installed"},
        headers=agent["h"],
    )
    assert r.json()["status"] == "failed" and r.json()["result"] == {
        "error": "Npcap is not installed"
    }
    again = client.post(
        f"{API}/agent/commands/{cmd.json()['id']}/result", json={"ok": True}, headers=agent["h"]
    )
    assert again.status_code == 409


# ---------------------------------------------------------------- isolation


def test_an_agent_only_sees_its_own_sites_commands(client, ana, eve, agent, home):
    circle = client.post(f"{API}/circles", json={"name": "Eve's"}, headers=eve.h).json()
    eves_site = client.post(
        f"{API}/circles/{circle['id']}/sites", json={"name": "Eve home"}, headers=eve.h
    ).json()
    eves_agent = pair(client, eve, eves_site["id"])
    eves_h = {"Authorization": f"Bearer {eves_agent['agent_token']}"}
    cmd = client.post(f"{API}/sites/{home['id']}/commands", json={"type": "scan"}, headers=ana.h)
    assert client.get(f"{API}/agent/commands?wait=0", headers=eves_h).json()["commands"] == []
    steal = client.post(
        f"{API}/agent/commands/{cmd.json()['id']}/result", json={"ok": True}, headers=eves_h
    )
    assert steal.status_code == 404
    assert client.get(f"{API}/commands/{cmd.json()['id']}", headers=eve.h).status_code == 404
    assert (
        client.post(
            f"{API}/sites/{home['id']}/commands", json={"type": "scan"}, headers=eve.h
        ).status_code
        == 404
    )


def test_device_type_guesses():
    assert infer_type("Samsung Electronics", "Galaxy-A15") == DeviceType.phone
    assert infer_type("Intel Corporate", "DESKTOP-01") == DeviceType.computer
    assert infer_type("HP Inc.", "Lab printer") == DeviceType.printer
    assert infer_type("ZTE Corporation", None) == DeviceType.router
    assert infer_type(None, None) == DeviceType.unknown
    assert infer_type("Apple", "front-door cam", is_gateway=True) == DeviceType.router


def test_the_long_poll_waits_when_nothing_is_queued(client, agent):
    import time

    start = time.monotonic()
    r = client.get(f"{API}/agent/commands?wait=2", headers=agent["h"])
    assert r.json()["commands"] == [] and time.monotonic() - start >= 1.9
