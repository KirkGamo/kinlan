"""Commands from the app to a site's agent: scan, ping test, diagnose, port check (Section 4.3).

Admins and owners send commands; any member can read their status and result.
"""

import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from app.agent_schemas import CommandIn, CommandOut
from app.authz import require_site
from app.commands import expire_stale, fail_if_overdue, to_out
from app.deps import DB, CurrentUser
from app.errors import ApiError
from app.models import Command, Device, Role
from app.schemas import ErrorOut

router = APIRouter(
    tags=["commands"],
    responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}, 404: {"model": ErrorOut}},
)


def _device_param(
    db: DB, site_id: uuid.UUID, params: dict[str, Any], *, required: bool
) -> Device | None:
    raw = params.get("device_id")
    if raw is None:
        if required:
            raise ApiError(400, "validation_error", "params.device_id: a device is required")
        return None
    try:
        device_id = uuid.UUID(str(raw))
    except ValueError as exc:
        raise ApiError(400, "validation_error", "params.device_id: not a valid id") from exc
    device = db.get(Device, device_id)
    if device is None or device.site_id != site_id:
        raise ApiError(404, "device_not_found", "That device isn't on this site.")
    return device


@router.post("/sites/{site_id}/commands", status_code=201, response_model=CommandOut)
def send_command(site_id: uuid.UUID, body: CommandIn, user: CurrentUser, db: DB) -> CommandOut:
    """Queue a command; the agent picks it up within about a second if it's online."""
    site = require_site(db, user, site_id, Role.admin)
    if body.type == "ping_test":
        count = body.params.get("count", 10)
        if not isinstance(count, int) or not 1 <= count <= 50:
            raise ApiError(400, "validation_error", "params.count: a whole number from 1 to 50")
        device = _device_param(db, site.id, body.params, required=True)
        if device.ip is None:
            raise ApiError(409, "device_has_no_address", "That device has no known IP address yet.")
        # The agent pings by address; the id ties the result back to the device's history.
        params = {
            "device_id": str(device.id),
            "ip": str(device.ip),
            "mac": device.mac,
            "count": count,
        }
    elif body.type == "port_check":
        device = _device_param(db, site.id, body.params, required=False)
        params = {"device_id": str(device.id), "ip": str(device.ip)} if device else {}
    else:
        params = {}
    cmd = Command(site_id=site.id, type=body.type, params=params, requested_by=user.id)
    db.add(cmd)
    db.commit()
    return to_out(cmd)


@router.get("/commands/{command_id}", response_model=CommandOut)
def get_command(command_id: uuid.UUID, user: CurrentUser, db: DB) -> CommandOut:
    """Status and result. A command nobody picked up within 2 minutes reads `expired`."""
    cmd = db.scalar(select(Command).where(Command.id == command_id))
    if cmd is None:
        raise ApiError(404, "command_not_found", "No such command.")
    try:
        require_site(db, user, cmd.site_id, Role.viewer)
    except ApiError as exc:
        raise ApiError(404, "command_not_found", "No such command.") from exc
    expire_stale(db, cmd.site_id)
    db.refresh(cmd)
    fail_if_overdue(cmd)
    db.commit()
    return to_out(cmd)
