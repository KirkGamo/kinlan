"""Opaque list cursors (plan, Section 4.3: `?limit=50&cursor=…`, newest first).

A cursor is the last row's sort key, a timestamp and the row id, base64url-encoded. Lists
continue with rows strictly before it, so ties on the timestamp are broken by the id.
"""

import base64
import uuid
from datetime import datetime

from app.errors import ApiError


def encode(stamp: datetime, ident: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{stamp.isoformat()}|{ident}".encode()).decode()


def decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        stamp, ident = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(stamp), uuid.UUID(ident)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ApiError(
            400, "bad_cursor", "That cursor isn't valid; start from the first page."
        ) from exc
