"""Command rules shared by the app side and the agent side (Section 4.3, command contracts)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.agent_schemas import CommandOut
from app.models import Command, CommandStatus

PICKUP_TIMEOUT = timedelta(minutes=2)  # not picked up by then → expired
RUN_TIMEOUT = {  # picked up but no result by then → failed
    "scan": timedelta(seconds=60),
    "ping_test": timedelta(seconds=30),
    "diagnose": timedelta(seconds=45),
    "port_check": timedelta(seconds=120),
}
EXPIRED_MESSAGE = "The agent didn't respond. Is the PC on?"


def expire_stale(db: Session, site_id, now: datetime | None = None) -> None:
    """Expire commands nobody picked up within 2 minutes (the app then shows EXPIRED_MESSAGE)."""
    now = now or datetime.now(UTC)
    db.execute(
        update(Command)
        .where(
            Command.site_id == site_id,
            Command.status == CommandStatus.pending,
            Command.created_at < now - PICKUP_TIMEOUT,
        )
        .values(status=CommandStatus.expired, finished_at=now, result={"error": EXPIRED_MESSAGE})
    )


def fail_if_overdue(cmd: Command, now: datetime | None = None) -> None:
    """A running command past its timeout (plus the pickup window) has failed."""
    now = now or datetime.now(UTC)
    limit = RUN_TIMEOUT.get(cmd.type, timedelta(seconds=60)) + PICKUP_TIMEOUT
    if cmd.status == CommandStatus.running and cmd.created_at < now - limit:
        cmd.status, cmd.finished_at = CommandStatus.failed, now
        cmd.result = {"error": "The agent started this but didn't finish in time."}


def to_out(cmd: Command) -> CommandOut:
    return CommandOut(
        id=cmd.id,
        site_id=cmd.site_id,
        type=cmd.type,
        params=cmd.params or {},
        status=cmd.status,
        result=cmd.result,
        created_at=cmd.created_at,
        finished_at=cmd.finished_at,
    )
