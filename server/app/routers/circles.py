"""Circles, members and invites (Sections 4.2 and 4.3).

Rules: anyone signed in can create a Circle and becomes its owner. Only owners invite, remove
others, change roles or delete the Circle. Anyone can leave. A Circle always keeps at least one
owner. Invite codes are 8 characters, single-use and expire after 7 days.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, Response
from sqlalchemy import func, select, update

from app.authz import RANK, owner_count, require_role
from app.deps import DB, CurrentUser
from app.errors import ApiError
from app.models import Circle, Device, Invite, Membership, Role, Site, User
from app.ratelimit import limiter
from app.schemas import (
    AcceptIn,
    CircleIn,
    CircleList,
    CircleOut,
    ErrorOut,
    InviteIn,
    InviteOut,
    MemberList,
    MemberOut,
    RoleIn,
)
from app.security import new_invite_code, normalise_code, sha256_hex

INVITE_TTL = timedelta(days=7)

router = APIRouter(
    tags=["circles"],
    responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}, 404: {"model": ErrorOut}},
)


def _circle_out(db: DB, circle: Circle, role: Role) -> CircleOut:
    members = db.scalar(
        select(func.count()).select_from(Membership).where(Membership.circle_id == circle.id)
    )
    sites = db.scalar(select(func.count()).select_from(Site).where(Site.circle_id == circle.id))
    return CircleOut(
        id=circle.id,
        name=circle.name,
        role=role,
        member_count=members,
        site_count=sites,
        created_at=circle.created_at,
    )


def _last_owner_guard(db: DB, circle_id: uuid.UUID, target: Membership) -> None:
    if target.role == Role.owner and owner_count(db, circle_id) == 1:
        raise ApiError(
            409,
            "last_owner",
            "A Circle needs at least one owner. Make someone else an owner first, "
            "or delete the Circle.",
        )


# ---------------------------------------------------------------- Circles


@router.get("/circles", response_model=CircleList)
def list_circles(user: CurrentUser, db: DB) -> CircleList:
    """Every Circle you belong to, with your role in each."""
    rows = db.execute(
        select(Circle, Membership.role)
        .join(Membership, Membership.circle_id == Circle.id)
        .where(Membership.user_id == user.id)
        .order_by(Circle.created_at)
    ).all()
    return CircleList(items=[_circle_out(db, c, role) for c, role in rows])


@router.post("/circles", status_code=201, response_model=CircleOut)
def create_circle(body: CircleIn, user: CurrentUser, db: DB) -> CircleOut:
    """Create a Circle. You become its owner."""
    circle = Circle(name=body.name, created_by=user.id)
    db.add(circle)
    db.flush()
    db.add(Membership(circle_id=circle.id, user_id=user.id, role=Role.owner))
    db.commit()
    return _circle_out(db, circle, Role.owner)


@router.delete("/circles/{circle_id}", status_code=204)
def delete_circle(circle_id: uuid.UUID, user: CurrentUser, db: DB) -> Response:
    """Delete the Circle with its sites, devices and history. Owners only."""
    require_role(db, user, circle_id, Role.owner)
    db.delete(db.get(Circle, circle_id))
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- members


@router.get("/circles/{circle_id}/members", response_model=MemberList)
def list_members(circle_id: uuid.UUID, user: CurrentUser, db: DB) -> MemberList:
    """Everyone in the Circle, owners first."""
    require_role(db, user, circle_id, Role.viewer)
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.circle_id == circle_id)
        .order_by(Membership.joined_at)
    ).all()
    items = [
        MemberOut(
            user_id=u.id,
            display_name=u.display_name,
            email=u.email,
            role=m.role,
            joined_at=m.joined_at,
        )
        for m, u in rows
    ]
    items.sort(key=lambda m: -RANK[m.role])  # stable: owners, admins, viewers, each by join date
    return MemberList(items=items)


def _target(db: DB, circle_id: uuid.UUID, user_id: uuid.UUID) -> Membership:
    target = db.get(Membership, (circle_id, user_id))
    if target is None:
        raise ApiError(404, "member_not_found", "That person isn't in this Circle.")
    return target


@router.patch(
    "/circles/{circle_id}/members/{user_id}",
    response_model=MemberOut,
    responses={409: {"model": ErrorOut}},
)
def change_role(
    circle_id: uuid.UUID, user_id: uuid.UUID, body: RoleIn, user: CurrentUser, db: DB
) -> MemberOut:
    """Change someone's role. Owners only; the last owner can't be demoted."""
    require_role(db, user, circle_id, Role.owner)
    target = _target(db, circle_id, user_id)
    if body.role != Role.owner:
        _last_owner_guard(db, circle_id, target)
    target.role = body.role
    db.commit()
    person = db.get(User, user_id)
    return MemberOut(
        user_id=person.id,
        display_name=person.display_name,
        email=person.email,
        role=target.role,
        joined_at=target.joined_at,
    )


@router.delete(
    "/circles/{circle_id}/members/{user_id}", status_code=204, responses={409: {"model": ErrorOut}}
)
def remove_member(circle_id: uuid.UUID, user_id: uuid.UUID, user: CurrentUser, db: DB) -> Response:
    """Leave the Circle (your own id), or remove someone (owners only)."""
    require_role(db, user, circle_id, Role.viewer if user_id == user.id else Role.owner)
    target = _target(db, circle_id, user_id)
    _last_owner_guard(db, circle_id, target)
    # A device can only belong to a member, so their devices here become shared.
    site_ids = select(Site.id).where(Site.circle_id == circle_id)
    db.execute(
        update(Device)
        .where(Device.site_id.in_(site_ids), Device.owner_user_id == user_id)
        .values(owner_user_id=None)
    )
    db.delete(target)
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- invites


@router.post("/circles/{circle_id}/invites", status_code=201, response_model=InviteOut)
def create_invite(circle_id: uuid.UUID, body: InviteIn, user: CurrentUser, db: DB) -> InviteOut:
    """Make a single-use invite code for the role you choose. Owners only."""
    require_role(db, user, circle_id, Role.owner)
    code = new_invite_code()
    invite = Invite(
        circle_id=circle_id,
        code_hash=sha256_hex(normalise_code(code)),
        role=body.role,
        expires_at=datetime.now(UTC) + INVITE_TTL,
    )
    db.add(invite)
    db.commit()
    return InviteOut(code=code, role=invite.role, expires_at=invite.expires_at)


@router.post(
    "/invites/accept",
    response_model=CircleOut,
    responses={400: {"model": ErrorOut}, 409: {"model": ErrorOut}, 429: {"model": ErrorOut}},
)
@limiter.limit("10/minute")
def accept_invite(request: Request, body: AcceptIn, user: CurrentUser, db: DB) -> CircleOut:
    """Join a Circle with an invite code."""
    invite = db.scalar(
        select(Invite)
        .where(Invite.code_hash == sha256_hex(normalise_code(body.code)))
        .with_for_update()
    )
    if invite is None or invite.used_at is not None:
        raise ApiError(404, "invite_not_found", "That invite code isn't valid or was already used.")
    now = datetime.now(UTC)
    if invite.expires_at <= now:
        raise ApiError(400, "invite_expired", "That invite code expired. Ask for a new one.")
    if db.get(Membership, (invite.circle_id, user.id)) is not None:
        raise ApiError(409, "already_member", "You're already in this Circle.")
    invite.used_by, invite.used_at = user.id, now
    db.add(Membership(circle_id=invite.circle_id, user_id=user.id, role=invite.role))
    db.commit()
    return _circle_out(db, db.get(Circle, invite.circle_id), invite.role)
