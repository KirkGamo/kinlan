"""Tests for the SQLite buffer, using temporary database files."""

import threading
from datetime import UTC, datetime, timedelta

import pytest

from kinlan_agent.buffer import Buffer

T0 = datetime(2026, 11, 20, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def buf(tmp_path):
    with Buffer(tmp_path / "buffer.db") as b:
        yield b


def test_items_come_back_oldest_first_and_unchanged(buf):
    buf.add("sample", {"target": "gateway", "rtt_ms": 1.5}, now=T0)
    buf.add_many("device", [{"ip": "192.168.1.1"}, {"ip": "192.168.1.8"}], now=T0)
    items = buf.peek()
    assert [i.kind for i in items] == ["sample", "device", "device"]
    assert items[0].payload == {"target": "gateway", "rtt_ms": 1.5}
    assert items[0].created_at == T0
    assert buf.count() == 3


def test_peek_limit_and_delete_after_upload(buf):
    ids = buf.add_many("sample", [{"n": n} for n in range(5)], now=T0)
    batch = buf.peek(limit=2)
    assert [i.payload["n"] for i in batch] == [0, 1]
    assert buf.delete(i.id for i in batch) == 2
    assert [i.payload["n"] for i in buf.peek()] == [2, 3, 4]
    assert buf.delete([]) == 0
    assert ids == sorted(ids)


def test_data_survives_reopening_the_file(tmp_path):
    path = tmp_path / "buffer.db"
    with Buffer(path) as b:
        b.add("sample", {"rtt_ms": 25.0}, now=T0)
    with Buffer(path) as b:
        assert b.count() == 1 and b.peek()[0].payload == {"rtt_ms": 25.0}


def test_failed_batch_is_rolled_back(buf):
    with pytest.raises(TypeError):
        buf.add_many("sample", [{"ok": 1}, {"bad": object()}], now=T0)  # not JSON-serializable
    assert buf.count() == 0


def test_prune_drops_items_older_than_seven_days(buf):
    buf.add("sample", {"old": True}, now=T0 - timedelta(days=8))
    buf.add("sample", {"old": False}, now=T0 - timedelta(days=1))
    assert buf.prune(now=T0) == 1
    assert [i.payload for i in buf.peek()] == [{"old": False}]


def test_prune_drops_oldest_items_when_over_size_limit(buf):
    big = "x" * 4000
    buf.add_many("sample", [{"n": n, "pad": big} for n in range(200)], now=T0)
    assert buf.data_bytes() > 400_000
    removed = buf.prune(now=T0, max_bytes=200_000, batch=10)
    assert removed > 0
    assert buf.data_bytes() <= 200_000
    remaining = [i.payload["n"] for i in buf.peek(limit=1000)]
    assert remaining == list(range(200 - len(remaining), 200))  # the newest rows survive


def test_open_outage_survives_restart_and_closing_queues_it(tmp_path):
    path = tmp_path / "buffer.db"
    with Buffer(path) as b:
        outage_id = b.open_outage(T0, "isp")
    with Buffer(path) as b:  # the PC restarted during the outage
        current = b.current_outage()
        assert current.id == outage_id and current.started_at == T0 and current.cause == "isp"
        payload = b.close_outage(outage_id, T0 + timedelta(minutes=4, seconds=12))
        assert payload == {
            "started_at": "2026-11-20T10:00:00Z",
            "ended_at": "2026-11-20T10:04:12Z",
            "cause": "isp",
        }
        assert b.current_outage() is None
        assert [(i.kind, i.payload) for i in b.peek()] == [("outage", payload)]


def test_close_unknown_outage_raises(buf):
    with pytest.raises(KeyError):
        buf.close_outage(999, T0)


def test_concurrent_writers_lose_nothing(buf):
    def writer(n):
        for i in range(50):
            buf.add("sample", {"writer": n, "i": i})

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert buf.count() == 200
