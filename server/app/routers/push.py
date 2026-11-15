"""Push tokens and each member's push switches (plan, Section 4.3, Push).

A phone registers its Expo push token after sign-in and removes it on sign-out. The switches
belong to the member in one Circle: outages, new devices and risky ports buzz by default; slow
internet and lost data stay in the app unless the member turns them on (briefs.md section 5).
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.authz import require_role
from app.deps import DB, CurrentUser
from app.models import PushToken, Role
from app.schemas import ErrorOut

router = APIRouter(
    tags=["push"],
    responses={401: {"model": ErrorOut}, 404: {"model": ErrorOut}},
)

ExpoToken = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, max_length=255, pattern=r"^Expo(nent)?PushToken\[.+\]$"
    ),
]


class PushTokenIn(BaseModel):
    token: ExpoToken = Field(examples=["ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]"])
    platform: Literal["android", "ios"] = "android"


class PushTokenOut(BaseModel):
    token: str
    platform: str


class NotificationSwitches(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    outages: bool = Field(description="The site is unreachable, or back online")
    new_devices: bool = Field(description="Someone new joined the network")
    security: bool = Field(description="A risky port is open on a device")
    performance: bool = Field(description="Slow internet or lost data")


class NotificationPatch(BaseModel):
    outages: bool | None = None
    new_devices: bool | None = None
    security: bool | None = None
    performance: bool | None = None


FIELDS = {
    "outages": "push_outages",
    "new_devices": "push_devices",
    "security": "push_security",
    "performance": "push_performance",
}


@router.post("/push-tokens", response_model=PushTokenOut, responses={400: {"model": ErrorOut}})
def register_token(body: PushTokenIn, user: CurrentUser, db: DB) -> PushTokenOut:
    """Register this phone for push. A token signed in under someone else moves to you."""
    row = db.get(PushToken, body.token)
    now = datetime.now(UTC)
    if row is None:
        row = PushToken(token=body.token, user_id=user.id, platform=body.platform, last_used_at=now)
        db.add(row)
    else:
        row.user_id, row.platform, row.last_used_at = user.id, body.platform, now
    db.commit()
    return PushTokenOut(token=row.token, platform=row.platform)


@router.delete("/push-tokens/{token}", status_code=204)
def remove_token(token: str, user: CurrentUser, db: DB) -> Response:
    """Stop pushing to this phone (sign-out). Removing a token that isn't yours does nothing."""
    row = db.get(PushToken, token)
    if row is not None and row.user_id == user.id:
        db.delete(row)
        db.commit()
    return Response(status_code=204)


def _switches(m) -> NotificationSwitches:
    return NotificationSwitches(**{k: getattr(m, v) for k, v in FIELDS.items()})


@router.get("/circles/{circle_id}/notifications", response_model=NotificationSwitches)
def get_switches(circle_id: uuid.UUID, user: CurrentUser, db: DB) -> NotificationSwitches:
    """Your push switches in this Circle."""
    return _switches(require_role(db, user, circle_id, Role.viewer))


@router.patch("/circles/{circle_id}/notifications", response_model=NotificationSwitches)
def update_switches(
    circle_id: uuid.UUID, body: NotificationPatch, user: CurrentUser, db: DB
) -> NotificationSwitches:
    """Change your own push switches; any member can, viewers included."""
    membership = require_role(db, user, circle_id, Role.viewer)
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(membership, FIELDS[field], value)
    db.commit()
    return _switches(membership)
