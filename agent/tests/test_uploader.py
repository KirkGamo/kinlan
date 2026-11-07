"""The uploader: nothing lost, resend-safe batches, backoff, and the server's refusals."""

import gzip
import json
import threading

import httpx
import pytest

from kinlan_agent.buffer import Buffer
from kinlan_agent.uploader import INFLIGHT_KEY, LAST_UPLOAD_KEY, Outcome, Uploader, build_payload

API = "https://api.example"


class FakeServer:
    """Records batches; answers with the queued status codes (then 200)."""

    def __init__(self, *statuses: int | Exception):
        self.statuses = list(statuses)
        self.batches: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret-token"
        assert request.headers["content-encoding"] == "gzip"
        body = json.loads(gzip.decompress(request.content))
        self.batches.append(body)
        status = self.statuses.pop(0) if self.statuses else 200
        if isinstance(status, Exception):
            raise status
        if status >= 400:
            return httpx.Response(
                status, json={"error": {"code": "x", "message": f"nope {status}"}}
            )
        return httpx.Response(status, json={"status": "stored"})


@pytest.fixture
def buffer():
    with Buffer(":memory:") as b:
        yield b


def uploader(buffer, server, **kw) -> Uploader:
    client = httpx.Client(transport=httpx.MockTransport(server.handler))
    return Uploader(buffer, API, "secret-token", client=client, **kw)


def sample(i: int) -> dict:
    return {
        "ts": f"2026-11-20T10:00:{i:02d}Z",
        "target": "internet",
        "ip": "8.8.8.8",
        "rtt_ms": 20.0,
        "ok": True,
    }


def test_an_empty_outbox_sends_nothing(buffer):
    server = FakeServer()
    assert uploader(buffer, server).send_once() is Outcome.EMPTY
    assert server.batches == []


def test_accepted_batches_leave_the_outbox(buffer):
    buffer.add_many("sample", [sample(i) for i in range(3)])
    server = FakeServer()
    up = uploader(buffer, server)
    assert up.send_once() is Outcome.SENT
    assert buffer.count() == 0 and buffer.get_meta(INFLIGHT_KEY) is None
    assert len(server.batches[0]["samples"]) == 3 and buffer.get_meta(LAST_UPLOAD_KEY)


def test_a_failed_send_is_retried_with_the_same_batch_id_and_rows(buffer):
    buffer.add_many("sample", [sample(i) for i in range(3)])
    server = FakeServer(httpx.ConnectError("offline"))
    up = uploader(buffer, server)
    assert up.send_once() is Outcome.RETRY and buffer.count() == 3
    buffer.add("sample", sample(9))  # new data arrives while offline
    assert up.send_once() is Outcome.SENT
    first, second = server.batches
    assert first["batch_id"] == second["batch_id"] and len(second["samples"]) == 3
    assert buffer.count() == 1  # the newer row waits for the next batch


def test_the_in_flight_batch_survives_a_restart(tmp_path):
    path = tmp_path / "buffer.db"
    with Buffer(path) as b:
        b.add_many("sample", [sample(i) for i in range(2)])
        uploader(b, FakeServer(httpx.ReadTimeout("slow"))).send_once()
        batch_id = b.get_meta(INFLIGHT_KEY).split()[0]
    with Buffer(path) as b:
        server = FakeServer()
        uploader(b, server).send_once()
    assert server.batches[0]["batch_id"] == batch_id


def test_server_errors_back_off_exponentially(buffer):
    buffer.add("sample", sample(0))
    up = uploader(buffer, FakeServer(503, 503, 503))
    waits = []
    for _ in range(3):
        assert up.send_once() is Outcome.RETRY
        waits.append(up.backoff_s())
    assert 1.6 <= waits[0] <= 2.4 and 6.4 <= waits[2] <= 9.6
    up.failures = 50
    assert up.backoff_s() <= 300 * 1.2


def test_an_unpaired_or_outdated_agent_stops_uploading(buffer):
    buffer.add("sample", sample(0))
    up = uploader(buffer, FakeServer(401))
    assert up.send_once() is Outcome.STOP and buffer.count() == 1
    assert up.stopped_reason == "nope 401"


def test_rows_the_server_will_never_accept_are_dropped_so_the_outbox_cannot_jam(buffer):
    buffer.add("sample", sample(0))
    up = uploader(buffer, FakeServer(400))
    assert up.send_once() is Outcome.SENT and buffer.count() == 0


def test_too_large_batches_are_split(buffer):
    buffer.add_many("sample", [sample(i) for i in range(8)])
    server = FakeServer(413)
    up = uploader(buffer, server, batch_size=8)
    assert up.send_once() is Outcome.RETRY
    assert up.send_once() is Outcome.SENT
    assert len(server.batches[1]["samples"]) == 4 and buffer.count() == 4


def test_payload_groups_outbox_kinds():
    from kinlan_agent.uploader import Batch

    rows = [
        type("Row", (), {"id": 1, "kind": "sample", "payload": sample(0)})(),
        type(
            "Row",
            (),
            {
                "id": 2,
                "kind": "scan",
                "payload": {
                    "netinfo": {
                        "local_ip": "192.168.1.13",
                        "cidr": "192.168.1.0/24",
                        "gateway": "192.168.1.1",
                    },
                    "devices": [{"mac": "64:f8:8a:00:00:01", "ip": "192.168.1.1"}],
                },
            },
        )(),
        type(
            "Row",
            (),
            {
                "id": 3,
                "kind": "outage",
                "payload": {
                    "started_at": "2026-11-20T09:41:00Z",
                    "ended_at": "2026-11-20T09:48:00Z",
                    "cause": "isp",
                },
            },
        )(),
        type("Row", (), {"id": 4, "kind": "mystery", "payload": {}})(),
    ]
    payload = build_payload(Batch("b-1", rows), version="0.1.0")
    assert payload["batch_id"] == "b-1" and payload["agent_version"] == "0.1.0"
    assert len(payload["samples"]) == 1 and len(payload["devices"]) == 1
    assert payload["netinfo"]["gateway"] == "192.168.1.1" and len(payload["outages"]) == 1


def test_run_drains_a_backlog_then_waits(buffer):
    buffer.add_many("sample", [sample(i) for i in range(5)])
    server = FakeServer()
    up = uploader(buffer, server, batch_size=2)
    stop = threading.Event()
    original = up.send_once

    def send_and_stop_when_empty():
        outcome = original()
        if outcome is Outcome.EMPTY:
            stop.set()
        return outcome

    up.send_once = send_and_stop_when_empty
    up.run(stop, interval_s=0.01)
    assert [len(b["samples"]) for b in server.batches] == [2, 2, 1] and buffer.count() == 0
