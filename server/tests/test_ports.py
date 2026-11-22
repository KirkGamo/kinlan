"""Port checks (#89): open ports, closed ones resolving, web admin pages as information."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.db import get_session_factory
from app.models import Alert, PortFinding
from tests.agent_fixtures import PC, PHONE, ROUTER, batch, iso, scan

API = "/api/v1"


def ingest(client, agent, **parts):
    r = client.post(f"{API}/agent/ingest", headers=agent["h"], json=batch(**parts))
    assert r.status_code == 200, r.text
    return r.json()


def check(macs, *open_ports, ports=(21, 23, 80, 445, 3389, 5900, 8080)):
    return {
        "checked_at": iso(datetime.now(UTC)),
        "ports": list(ports),
        "macs": list(macs),
        "open": [{"mac": m, "port": p, "service": s} for m, p, s in open_ports],
    }


def device_id(client, owner, site_id, mac):
    devices = client.get(f"{API}/sites/{site_id}/devices", headers=owner.h).json()["items"]
    return next(d["id"] for d in devices if d["mac"] == mac)


def open_findings():
    with get_session_factory()() as db:
        return {
            (f.port, f.service)
            for f in db.scalars(select(PortFinding).where(PortFinding.resolved_at.is_(None)))
        }


def risky_alerts(open_only=True):
    with get_session_factory()() as db:
        q = select(Alert).where(Alert.type == "risky_port")
        if open_only:
            q = q.where(Alert.resolved_at.is_(None))
        return list(db.scalars(q))


def test_a_closed_port_resolves_its_finding_and_alert(client, agent):
    ingest(client, agent, devices=scan(ROUTER, PC))
    macs = [ROUTER[0], PC[0]]
    ingest(client, agent, port_checks=[check(macs, (PC[0], 445, "smb"))])
    assert open_findings() == {(445, "smb")}
    [alert] = risky_alerts()
    assert alert.title == "SMB is open on DESKTOP-01"

    ingest(client, agent, port_checks=[check(macs)])  # turned off on the PC
    assert open_findings() == set()
    assert risky_alerts() == []


def test_a_port_not_tried_stays_open(client, agent):
    """A check of one device, or of other ports, says nothing about the rest."""
    ingest(client, agent, devices=scan(ROUTER, PC))
    ingest(client, agent, port_checks=[check([PC[0]], (PC[0], 3389, "rdp"))])
    ingest(client, agent, port_checks=[check([ROUTER[0]])])  # only the router this time
    ingest(client, agent, port_checks=[check([PC[0]], ports=(21, 23))])  # 3389 not tried
    assert open_findings() == {(3389, "rdp")}


def test_web_admin_pages_are_information_not_risk(client, ana, agent, home):
    ingest(client, agent, devices=scan(ROUTER, PC))
    ingest(client, agent, port_checks=[check([ROUTER[0]], (ROUTER[0], 80, "http"))])
    assert risky_alerts() == []  # no alert for a router's admin page
    router_id = device_id(client, ana, home["id"], ROUTER[0])
    detail = client.get(f"{API}/devices/{router_id}", headers=ana.h).json()
    assert detail["open_risky_ports"] == 0
    assert detail["risky_ports"][0]["port"] == 80 and detail["risky_ports"][0]["info"] is True
    summary = client.get(f"{API}/sites/{home['id']}/summary", headers=ana.h).json()
    assert all(d["factor"] != "ports" for d in summary["deductions"])


def test_older_agents_that_only_send_findings_still_work(client, agent):
    ingest(client, agent, devices=scan(ROUTER, PC))
    ingest(client, agent, port_findings=[{"mac": ROUTER[0], "port": 23, "service": "telnet"}])
    [alert] = risky_alerts()
    assert alert.severity == "critical"


def test_a_device_check_round_trip(client, ana, agent, home):
    ingest(client, agent, devices=scan(ROUTER, PC, PHONE))
    pc = device_id(client, ana, home["id"], PC[0])
    cmd = client.post(
        f"{API}/sites/{home['id']}/commands",
        json={"type": "port_check", "params": {"device_id": pc}},
        headers=ana.h,
    ).json()
    assert cmd["params"]["targets"] == [{"mac": PC[0], "ip": PC[1]}]
    [picked] = client.get(f"{API}/agent/commands?wait=0", headers=agent["h"]).json()["commands"]
    result = {"ports": [21, 23, 80, 445, 3389, 5900, 8080], "macs": [PC[0]],
              "open": [{"mac": PC[0], "port": 445, "service": "smb"}], "duration_ms": 512}
    r = client.post(f"{API}/agent/commands/{picked['id']}/result", headers=agent["h"],
                    json={"ok": True, "result": result})
    assert r.status_code == 200 and r.json()["status"] == "done"
    detail = client.get(f"{API}/devices/{pc}", headers=ana.h).json()
    assert [p["port"] for p in detail["risky_ports"]] == [445]  # stored at once, not next upload
    assert [a.title for a in risky_alerts()] == ["SMB is open on DESKTOP-01"]


def test_a_whole_site_check_targets_every_device_with_an_address(client, ana, agent, home):
    ingest(client, agent, devices=scan(ROUTER, PC, PHONE))
    cmd = client.post(
        f"{API}/sites/{home['id']}/commands", json={"type": "port_check", "params": {}},
        headers=ana.h,
    ).json()
    assert {t["mac"] for t in cmd["params"]["targets"]} == {ROUTER[0], PC[0], PHONE[0]}
    assert "device_id" not in cmd["params"]


def test_a_bad_port_check_result_is_refused(client, ana, agent, home):
    ingest(client, agent, devices=scan(ROUTER))
    client.post(f"{API}/sites/{home['id']}/commands", json={"type": "port_check"}, headers=ana.h)
    [picked] = client.get(f"{API}/agent/commands?wait=0", headers=agent["h"]).json()["commands"]
    r = client.post(f"{API}/agent/commands/{picked['id']}/result", headers=agent["h"],
                    json={"ok": True, "result": {"ports": "all of them"}})
    assert r.status_code == 400


def test_a_whole_site_check_skips_offline_devices_and_reused_addresses(client, ana, agent, home):
    """An old record that still holds the router's address isn't checked as the router."""
    old_box = ("aa:bb:cc:00:00:09", ROUTER[1], None, "zte corporation")
    ingest(client, agent, devices=scan(old_box, PC))
    with get_session_factory()() as db:
        from app.models import Device

        box = db.scalar(select(Device).where(Device.mac == old_box[0]))
        box.online = False  # gone for a while; the router now has its address
        box.last_seen_at = datetime(2026, 11, 1, tzinfo=UTC)
        db.commit()
    ingest(client, agent, devices=scan(ROUTER, PC))
    with get_session_factory()() as db:
        db.scalar(select(Device).where(Device.mac == old_box[0])).online = True  # stale flag
        db.commit()
    cmd = client.post(
        f"{API}/sites/{home['id']}/commands", json={"type": "port_check"}, headers=ana.h
    ).json()
    by_ip = {t["ip"]: t["mac"] for t in cmd["params"]["targets"]}
    assert by_ip[ROUTER[1]] == ROUTER[0] and len(cmd["params"]["targets"]) == 2
