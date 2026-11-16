"""Push delivery through Expo's push service (plan, Sections 4.4 and 4.5).

Alerts are stored first; this module sends them afterwards, so ingest never waits on the network:

- :func:`dispatch` (every 15 s) sends each alert not pushed yet to every member of the site's
  Circle who has a phone registered and that kind of alert switched on, then marks it pushed.
  An alert older than :data:`FRESH_FOR` is marked without sending: late news is noise.
- :func:`check_receipts` (every 15 min) asks Expo how each delivery went and deletes tokens Expo
  reports as no longer registered (the app was uninstalled, or the phone was reset).

The two network calls are module-level functions so tests can replace them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import Alert, Membership, PushTicket, PushToken, Site

log = logging.getLogger("kinlan.push")

SEND_URL = "https://exp.host/--/api/v2/push/send"
RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"
FRESH_FOR = timedelta(minutes=30)
RECEIPT_AFTER = timedelta(minutes=15)  # Expo's receipts are ready within about 15 minutes
TICKET_TTL = timedelta(days=1)  # Expo keeps receipts for a day
SEND_CHUNK = 100  # Expo's limit per request
RECEIPT_CHUNK = 300

# Which member switch governs each alert type (briefs.md section 5).
SWITCH = {
    "unreachable": "push_outages",
    "back_online": "push_outages",
    "new_device": "push_devices",
    "risky_port": "push_security",
    "high_latency": "push_performance",
    "packet_loss": "push_performance",
}

Messages = list[dict[str, Any]]
Sender = Callable[[Messages], list[dict[str, Any]]]
ReceiptFetcher = Callable[[list[str]], dict[str, dict[str, Any]]]


def send_messages(messages: Messages) -> list[dict[str, Any]]:
    """POST a chunk of messages to Expo; returns one ticket per message, in order."""
    r = httpx.post(
        SEND_URL,
        json=messages,
        headers={"Accept": "application/json", "Accept-Encoding": "gzip"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["data"]


def fetch_receipts(ids: list[str]) -> dict[str, dict[str, Any]]:
    """Receipts for ticket ids Expo has finished with (missing ids aren't ready yet)."""
    r = httpx.post(RECEIPTS_URL, json={"ids": ids}, timeout=15)
    r.raise_for_status()
    return r.json()["data"]


def link_for(alert: Alert) -> str:
    """Where tapping the notification goes in the app."""
    if alert.type in ("new_device", "risky_port") and alert.subject_ref:
        return f"/devices?device={alert.subject_ref.split(':')[0]}"
    if alert.type == "unreachable":
        # Overview opens with the failing light's sheet; `at` makes each push a new link.
        return f"/?light=failing&at={alert.id}"
    return "/alerts"


def recipients(db: Session, alert: Alert) -> list[str]:
    """Push tokens of the Circle's members who want this kind of alert."""
    switch = SWITCH.get(alert.type)
    if switch is None:
        return []
    site = db.get(Site, alert.site_id)
    if site is None:
        return []
    return list(
        db.scalars(
            select(PushToken.token)
            .join(Membership, Membership.user_id == PushToken.user_id)
            .where(Membership.circle_id == site.circle_id, getattr(Membership, switch).is_(True))
            .order_by(PushToken.token)
        )
    )


def message(alert: Alert, token: str) -> dict[str, Any]:
    return {
        "to": token,
        "title": alert.title,
        "body": alert.body,
        "data": {"url": link_for(alert), "alertId": str(alert.id), "siteId": str(alert.site_id)},
        "channelId": alert.severity,  # the app creates channels critical, warning and info
        "priority": "high" if alert.severity == "critical" else "default",
        "sound": "default",
    }


def _chunks(items: list, size: int) -> Iterable[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _forget(db: Session, tokens: Iterable[str]) -> int:
    tokens = list(set(tokens))
    if not tokens:
        return 0
    return db.execute(delete(PushToken).where(PushToken.token.in_(tokens))).rowcount


def dispatch(db: Session, now: datetime | None = None, sender: Sender | None = None) -> int:
    """Push every alert not pushed yet; returns how many messages Expo accepted."""
    now = now or datetime.now(UTC)
    sender = sender or send_messages
    pending = list(
        db.scalars(
            select(Alert)
            .where(Alert.pushed_at.is_(None))
            .order_by(Alert.created_at)
            .limit(200)
            .with_for_update(skip_locked=True)
        )
    )
    accepted = 0
    for alert in pending:
        if alert.created_at < now - FRESH_FOR:
            alert.pushed_at = now  # too late to be useful; never buzz about old news
            continue
        tokens = recipients(db, alert)
        dead: list[str] = []
        try:
            for chunk in _chunks(tokens, SEND_CHUNK):
                tickets = sender([message(alert, t) for t in chunk])
                for token, ticket in zip(chunk, tickets, strict=False):
                    if ticket.get("status") == "ok" and ticket.get("id"):
                        db.add(PushTicket(ticket_id=ticket["id"], token=token, created_at=now))
                        accepted += 1
                    elif (ticket.get("details") or {}).get("error") == "DeviceNotRegistered":
                        dead.append(token)
                    else:
                        log.warning("push to a token failed: %s", ticket.get("message"))
        except httpx.HTTPError as exc:
            log.warning("Expo push unavailable, retrying next run: %s", exc)
            break  # leave this and later alerts unpushed; FRESH_FOR caps the retries
        if tokens:
            db.execute(
                update(PushToken).where(PushToken.token.in_(tokens)).values(last_used_at=now)
            )
        _forget(db, dead)
        alert.pushed_at = now
    db.commit()
    return accepted


def check_receipts(
    db: Session, now: datetime | None = None, fetcher: ReceiptFetcher | None = None
) -> dict[str, int]:
    """Read Expo's receipts for tickets old enough to have one; delete dead tokens."""
    now = now or datetime.now(UTC)
    fetcher = fetcher or fetch_receipts
    due = list(db.scalars(select(PushTicket).where(PushTicket.created_at < now - RECEIPT_AFTER)))
    removed = checked = 0
    for chunk in _chunks(due, RECEIPT_CHUNK):
        try:
            receipts = fetcher([t.ticket_id for t in chunk])
        except httpx.HTTPError as exc:
            log.warning("Expo receipts unavailable, retrying later: %s", exc)
            break
        dead = []
        for ticket in chunk:
            receipt = receipts.get(ticket.ticket_id)
            if receipt is None and ticket.created_at > now - TICKET_TTL:
                continue  # not ready yet; ask again next run
            if receipt and (receipt.get("details") or {}).get("error") == "DeviceNotRegistered":
                dead.append(ticket.token)
            db.delete(ticket)
            checked += 1
        removed += _forget(db, dead)
    db.commit()
    return {"checked": checked, "tokens_removed": removed}
