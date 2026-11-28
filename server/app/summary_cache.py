"""A short cache of each site's Overview summary (technical plan §9, API performance).

Every member with the Overview open polls `/sites/{id}/summary` every 5 s, and each answer
costs about a dozen queries. The answer is the same for every member, so it's computed once per
site and served to the others for up to `TTL_S` seconds. Concurrent requests for a site that
isn't cached wait for the one computing it instead of all computing it (single flight).

The role check still runs on every request: only the site's data is cached, never who may
see it.

Any committed write clears the whole cache, so a reading never outlives the change it shows (an
ingest, an acknowledged alert, a trusted device). Writes are rare next to reads, so clearing all
sites is simpler than working out which ones a write touched, and can't miss one. A counter of
writes keeps a summary computed while a write committed from being stored.

The cache lives in the process: Render runs one uvicorn process. With several, each would keep
its own and see only its own writes, so this would need a shared store first.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable

from sqlalchemy import event
from sqlalchemy.orm import Session, SessionTransaction

TTL_S = 10.0

_entries: dict[uuid.UUID, tuple[float, bytes]] = {}
_locks: dict[uuid.UUID, threading.Lock] = {}
_guard = threading.Lock()
_generation = 0
_clock: Callable[[], float] = time.monotonic


def get_or_compute(site_id: uuid.UUID, compute: Callable[[], bytes]) -> bytes:
    """The site's cached summary, or `compute()`'s, stored unless a write committed meanwhile."""
    hit = _fresh(site_id)
    if hit is not None:
        return hit
    with _guard:
        lock = _locks.setdefault(site_id, threading.Lock())
    with lock:
        hit = _fresh(site_id)  # whoever held the lock may have just computed it
        if hit is not None:
            return hit
        started = _generation
        body = compute()
        with _guard:
            if _generation == started:
                _entries[site_id] = (_clock() + TTL_S, body)
        return body


def clear() -> None:
    """Forget every site's summary (called after each committed write)."""
    global _generation
    with _guard:
        _generation += 1
        _entries.clear()


def _fresh(site_id: uuid.UUID) -> bytes | None:
    entry = _entries.get(site_id)
    if entry is None or entry[0] <= _clock():
        return None
    return entry[1]


# ---------------------------------------------------------------- write detection

_WROTE = "kinlan_wrote"


@event.listens_for(Session, "after_flush")
def _flushed(session: Session, _context) -> None:
    session.info[_WROTE] = True  # ORM objects added, changed or deleted


@event.listens_for(Session, "do_orm_execute")
def _executed(state) -> None:
    if not state.is_select:
        state.session.info[_WROTE] = True  # Core-style insert / update / delete on a session


@event.listens_for(Session, "after_commit")
def _committed(session: Session) -> None:
    if session.info.pop(_WROTE, False):
        clear()


@event.listens_for(Session, "after_soft_rollback")
def _rolled_back(session: Session, _previous: SessionTransaction) -> None:
    session.info.pop(_WROTE, None)  # nothing reached the database
