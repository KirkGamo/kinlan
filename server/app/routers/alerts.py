"""Alerts and per-site alert settings (Sections 4.3 and 4.4).

Any member reads alerts; admins and owners acknowledge them and change thresholds.
Lists are newest first with cursor pagination (`?limit=50&cursor=…`).
"""

import base64
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Query
from sqlalchemy import select, tuple_

from app.alerts import settings_for
from app.authz import require_site
from app.deps import DB, CurrentUser
from app.errors import ApiError
from app.models import Alert, Role
from app.schemas import AlertList, AlertOut, AlertSettingsOut, AlertSettingsPatch, ErrorOut

router = APIRouter(
    tags=["alerts"],
    responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}, 404: {"model": ErrorOut}},
)


def _encode(alert: Alert) -> str:
    return base64.urlsafe_b64encode(f"{alert.created_at.isoformat()}|{alert.id}".encode()).decode()


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        stamp, ident = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(stamp), uuid.UUID(ident)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ApiError(
            400, "bad_cursor", "That cursor isn't valid; start from the first page."
        ) from exc


@router.get("/sites/{site_id}/alerts", response_model=AlertList)
def list_alerts(
    site_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    status: Literal["open", "resolved", "all"] = "all",
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
) -> AlertList:
    """`open` = not acknowledged and not resolved; `resolved` = acknowledged or resolved."""
    site = require_site(db, user, site_id, Role.viewer)
    query = select(Alert).where(Alert.site_id == site.id)
    is_open = Alert.acked_at.is_(None) & Alert.resolved_at.is_(None)
    if status == "open":
        query = query.where(is_open)
    elif status == "resolved":
        query = query.where(~is_open)
    if cursor:
        query = query.where(tuple_(Alert.created_at, Alert.id) < tuple_(*_decode(cursor)))
    rows = list(
        db.scalars(query.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit + 1))
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return AlertList(
        items=[AlertOut.model_validate(a) for a in rows],
        next_cursor=_encode(rows[-1]) if more and rows else None,
    )


@router.post("/alerts/{alert_id}/ack", response_model=AlertOut)
def acknowledge(alert_id: uuid.UUID, user: CurrentUser, db: DB) -> AlertOut:
    """Acknowledge an alert ("I've seen it"). Admins and owners; doing it twice is harmless."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise ApiError(404, "alert_not_found", "No such alert.")
    try:
        require_site(db, user, alert.site_id, Role.admin)
    except ApiError as exc:
        if exc.status == 404:
            raise ApiError(404, "alert_not_found", "No such alert.") from exc
        raise
    if alert.acked_at is None:
        alert.acked_at, alert.acked_by = datetime.now(UTC), user.id
        db.commit()
    return AlertOut.model_validate(alert)


@router.get("/sites/{site_id}/alert-settings", response_model=AlertSettingsOut)
def get_alert_settings(site_id: uuid.UUID, user: CurrentUser, db: DB) -> AlertSettingsOut:
    site = require_site(db, user, site_id, Role.viewer)
    settings = settings_for(db, site)
    db.commit()
    return AlertSettingsOut.model_validate(settings)


@router.patch("/sites/{site_id}/alert-settings", response_model=AlertSettingsOut)
def update_alert_settings(
    site_id: uuid.UUID, body: AlertSettingsPatch, user: CurrentUser, db: DB
) -> AlertSettingsOut:
    """Change when this site alerts. Admins and owners."""
    site = require_site(db, user, site_id, Role.admin)
    settings = settings_for(db, site)
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(settings, field, value)
    db.commit()
    return AlertSettingsOut.model_validate(settings)
