"""PDF reports (plan, Sections 4.3 and 4.7): make one for a site, then download it.

Any member can make and read reports (the role matrix lets viewers see reports). The PDF opens
in the phone's browser or viewer, which can't send the app's access token, so every report
comes with a download link signed for that report alone and valid for 10 minutes. Asking for
the report again gives a fresh link. Reports are kept 30 days (the retention job).
"""

import hmac
import time
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from app import reports
from app.authz import require_site
from app.deps import DB, CurrentUser
from app.errors import ApiError
from app.models import Report, Role, Site
from app.ratelimit import limiter
from app.schemas import ErrorOut
from app.security import keyed_hash

router = APIRouter(
    tags=["reports"],
    responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}, 404: {"model": ErrorOut}},
)

LINK_SECONDS = 600
Span = Literal["24h", "7d", "30d"]


class ReportIn(BaseModel):
    range: Span = "24h"


class ReportOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    range: Span
    range_start: datetime
    range_end: datetime
    created_at: datetime
    filename: str
    download_url: str  # relative to the API root; signed, valid for 10 minutes


def _signature(report_id: uuid.UUID, expires: int) -> str:
    return keyed_hash(f"report:{report_id}:{expires}")


def download_token(report_id: uuid.UUID, now: float | None = None) -> str:
    expires = int((now or time.time()) + LINK_SECONDS)
    return f"{expires}.{_signature(report_id, expires)}"


def _span(r: Report) -> Span:
    hours = (r.range_end - r.range_start).total_seconds() / 3600
    return "24h" if hours <= 24.5 else "7d" if hours <= 7 * 24 + 1 else "30d"


def _filename(r: Report, site: Site) -> str:
    stamp = r.range_end.astimezone(reports.zone_of(site)).strftime("%Y-%m-%d")
    safe = "".join(c if c.isalnum() else "-" for c in site.name).strip("-") or "site"
    return f"KinLAN-{safe}-{_span(r)}-{stamp}.pdf"


def _out(r: Report, site: Site) -> ReportOut:
    return ReportOut(
        id=r.id,
        site_id=r.site_id,
        range=_span(r),
        range_start=r.range_start,
        range_end=r.range_end,
        created_at=r.created_at,
        filename=_filename(r, site),
        download_url=f"/api/v1/reports/{r.id}.pdf?token={download_token(r.id)}",
    )


@router.post("/sites/{site_id}/reports", status_code=201, response_model=ReportOut)
@limiter.limit("10/minute")
def create_report(
    request: Request, site_id: uuid.UUID, body: ReportIn, user: CurrentUser, db: DB
) -> ReportOut:
    """Make the PDF report for the last 24 hours, 7 days or 30 days."""
    site = require_site(db, user, site_id, Role.viewer)
    now = datetime.now(UTC)
    data = reports.gather(db, site, body.range, now)
    report = Report(
        site_id=site.id,
        requested_by=user.id,
        range_start=data.start,
        range_end=data.end,
        created_at=now,
        pdf=reports.render(data),
    )
    db.add(report)
    db.commit()
    return _out(report, site)


# Registered before /reports/{report_id}, which would otherwise match "<id>.pdf" and reject it.
@router.get(
    "/reports/{report_id}.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def download_report(
    report_id: uuid.UUID, db: DB, token: str = Query(..., description="From download_url")
) -> Response:
    """The PDF itself. Needs the signed token from `download_url` instead of a sign-in."""
    expires_text, _, signature = token.partition(".")
    valid = (
        expires_text.isdigit()
        and int(expires_text) >= time.time()
        and hmac.compare_digest(signature, _signature(report_id, int(expires_text)))
    )
    if not valid:
        raise ApiError(
            403, "link_expired", "This download link has expired. Open the report again."
        )
    report = db.get(Report, report_id)
    site = db.get(Site, report.site_id) if report else None
    if report is None or report.pdf is None or site is None:
        raise ApiError(404, "report_not_found", "That report doesn't exist or has expired.")
    return Response(
        content=report.pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{_filename(report, site)}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: uuid.UUID, user: CurrentUser, db: DB) -> ReportOut:
    """A report's details, with a fresh download link."""
    report = db.get(Report, report_id)
    if report is None:
        raise ApiError(404, "report_not_found", "That report doesn't exist or has expired.")
    site = require_site(db, user, report.site_id, Role.viewer)
    return _out(report, site)
