"""Authorization: every read or write of Circle data goes through a membership check.

Not a member → 404 (another Circle's data is indistinguishable from data that doesn't exist).
A member whose role is too low → 403.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Membership, Role, User

RANK = {Role.viewer: 0, Role.admin: 1, Role.owner: 2}
ROLE_WORD = {Role.viewer: "a viewer", Role.admin: "an admin", Role.owner: "an owner"}


def require_role(db: Session, user: User, circle_id: uuid.UUID, min_role: Role) -> Membership:
    """Return the caller's membership in the Circle, or raise 404 / 403."""
    membership = db.get(Membership, (circle_id, user.id))
    if membership is None:
        raise ApiError(404, "circle_not_found", "That Circle doesn't exist or you're not in it.")
    if RANK[membership.role] < RANK[min_role]:
        raise ApiError(403, "forbidden", f"Only {ROLE_WORD[min_role]} or higher can do that.")
    return membership


def owner_count(db: Session, circle_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.circle_id == circle_id, Membership.role == Role.owner)
    )
