"""The role matrix of technical plan Section 4.2, row by row, for an owner, an admin and a
viewer of the same Circle (issue #94). Each case builds a fresh Circle, so destructive actions
(removing a member, deleting the Circle) can't affect the others."""

import pytest

from tests.agent_fixtures import PC, PHONE, ROUTER, batch, pair, scan

API = "/api/v1"

OWNER, ADMIN, VIEWER = "owner", "admin", "viewer"


@pytest.fixture
def world(client, ana, jun, eve):
    """Ana owns "CCS Lab" with one paired site; Jun is an admin and Eve a viewer. The site has
    devices from a baseline scan and a "new device" alert from a later one."""
    circle = client.post(f"{API}/circles", json={"name": "CCS Lab"}, headers=ana.h).json()
    site = client.post(f"{API}/circles/{circle['id']}/sites", json={"name": "Lab"}, headers=ana.h)
    site = site.json()
    for person, role in ((jun, ADMIN), (eve, VIEWER)):
        invite = client.post(
            f"{API}/circles/{circle['id']}/invites", json={"role": role}, headers=ana.h
        ).json()
        assert client.post(
            f"{API}/invites/accept", json={"code": invite["code"]}, headers=person.h
        ).status_code == 200
    agent = {"Authorization": f"Bearer {pair(client, ana, site['id'])['agent_token']}"}
    for devices in ((ROUTER, PC), (ROUTER, PC, PHONE)):  # baseline, then a stranger
        body = batch(netinfo={"gateway": "192.168.1.1"}, devices=scan(*devices))
        r = client.post(f"{API}/agent/ingest", json=body, headers=agent)
        assert r.status_code == 200, r.text
    devices = client.get(f"{API}/sites/{site['id']}/devices", headers=ana.h).json()["items"]
    alerts = client.get(f"{API}/sites/{site['id']}/alerts", headers=ana.h).json()["items"]
    return {
        "circle": circle["id"],
        "site": site["id"],
        "device": devices[0]["id"],
        "alert": alerts[0]["id"],
        "people": {OWNER: ana, ADMIN: jun, VIEWER: eve},
        "ids": {OWNER: ana.id, ADMIN: jun.id, VIEWER: eve.id},
    }


def view(c, w, h):
    s = w["site"]
    paths = [f"/sites/{s}", f"/sites/{s}/summary", f"/sites/{s}/devices", f"/sites/{s}/latency",
             f"/sites/{s}/outages", f"/sites/{s}/alerts", f"/sites/{s}/diagnoses",
             f"/devices/{w['device']}", f"/circles/{w['circle']}/members"]
    return [c.get(API + p, headers=h) for p in paths]


def run_commands(c, w, h):
    return [c.post(f"{API}/sites/{w['site']}/commands", json={"type": t}, headers=h)
            for t in ("scan", "diagnose", "port_check")]


def edit_devices_and_alerts(c, w, h):
    return [
        c.patch(f"{API}/devices/{w['device']}", json={"custom_name": "Lab router"}, headers=h),
        c.patch(f"{API}/devices/{w['device']}", json={"trusted": True}, headers=h),
        c.post(f"{API}/alerts/{w['alert']}/ack", headers=h),
    ]


def manage_sites(c, w, h):
    return [
        c.post(f"{API}/circles/{w['circle']}/sites", json={"name": "Lab 2"}, headers=h),
        c.post(f"{API}/sites/{w['site']}/pairing-code", headers=h),
        c.patch(f"{API}/sites/{w['site']}/alert-settings", json={"latency_ms": 150}, headers=h),
    ]


def manage_members(c, w, h):
    """On someone else: the viewer, or the admin when the viewer is the one asking."""
    circle = w["circle"]
    other = w["ids"][ADMIN if w["caller"] == VIEWER else VIEWER]
    return [
        c.post(f"{API}/circles/{circle}/invites", json={"role": "viewer"}, headers=h),
        c.patch(f"{API}/circles/{circle}/members/{other}", json={"role": "admin"}, headers=h),
        c.delete(f"{API}/circles/{circle}/members/{other}", headers=h),
    ]


def leave(c, w, h):
    """Anyone but the last owner may leave (plan Section 4.2, Circle rules)."""
    return [c.delete(f"{API}/circles/{w['circle']}/members/{w['ids'][w['caller']]}", headers=h)]


def delete_circle(c, w, h):
    return [c.delete(f"{API}/circles/{w['circle']}", headers=h)]


# action, then who may do it (plan Section 4.2)
MATRIX = [
    ("view sites, devices, charts, alerts", view, {OWNER, ADMIN, VIEWER}),
    ("run scan / diagnose / port check", run_commands, {OWNER, ADMIN}),
    ("rename devices, mark trusted, acknowledge", edit_devices_and_alerts, {OWNER, ADMIN}),
    ("create sites, pairing codes, thresholds", manage_sites, {OWNER, ADMIN}),
    ("invite, change roles, remove members", manage_members, {OWNER}),
    ("delete the Circle", delete_circle, {OWNER}),
    ("leave the Circle", leave, {ADMIN, VIEWER}),  # the only owner must hand over first
]


@pytest.mark.parametrize("role", [OWNER, ADMIN, VIEWER])
@pytest.mark.parametrize(("action", "calls", "allowed"), MATRIX, ids=[m[0] for m in MATRIX])
def test_role_matrix(client, world, role, action, calls, allowed):
    world["caller"] = role
    responses = calls(client, world, world["people"][role].h)
    codes = [r.status_code for r in responses]
    if role in allowed:
        assert all(200 <= code < 300 for code in codes), (action, role, codes)
    elif action == "leave the Circle":
        assert codes == [409], codes  # the last owner can't leave
    else:
        assert all(code == 403 for code in codes), (action, role, codes)
        assert all(r.json()["error"]["code"] == "forbidden" for r in responses)
