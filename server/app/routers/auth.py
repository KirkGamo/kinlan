"""Auth: register, login, refresh (rotating), logout, and the signed-in account (Section 4.2)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.deps import DB, CurrentUser
from app.errors import ApiError
from app.models import Membership, RefreshToken, Role, User
from app.ratelimit import limiter
from app.schemas import ErrorOut, LoginIn, RefreshIn, RegisterIn, TokenPair, UserOut
from app.security import (
    ACCESS_TTL,
    REFRESH_TTL,
    create_access_token,
    hash_password,
    new_opaque_token,
    sha256_hex,
    verify_password,
)

router = APIRouter(tags=["auth"], responses={400: {"model": ErrorOut}, 401: {"model": ErrorOut}})


def _issue_tokens(db: DB, user: User) -> tuple[TokenPair, RefreshToken]:
    raw = new_opaque_token()
    row = RefreshToken(
        user_id=user.id, token_hash=sha256_hex(raw), expires_at=datetime.now(UTC) + REFRESH_TTL
    )
    db.add(row)
    db.flush()
    pair = TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=raw,
        expires_in=int(ACCESS_TTL.total_seconds()),
    )
    return pair, row


@router.post(
    "/auth/register",
    status_code=201,
    response_model=TokenPair,
    responses={409: {"model": ErrorOut}},
)
@limiter.limit("5/minute")
def register(request: Request, body: RegisterIn, db: DB) -> TokenPair:
    """Create an account and sign in."""
    user = User(
        email=body.email, password_hash=hash_password(body.password), display_name=body.display_name
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "email_taken", "An account with that email already exists.") from exc
    pair, _ = _issue_tokens(db, user)
    db.commit()
    return pair


@router.post("/auth/login", response_model=TokenPair, responses={429: {"model": ErrorOut}})
@limiter.limit("10/minute")
def login(request: Request, body: LoginIn, db: DB) -> TokenPair:
    """Sign in with email and password. A wrong email and a wrong password look the same."""
    user = db.scalar(select(User).where(User.email == body.email))
    if not verify_password(body.password, user.password_hash if user else None) or user is None:
        raise ApiError(401, "invalid_credentials", "That email and password don't match.")
    pair, _ = _issue_tokens(db, user)
    db.commit()
    return pair


@router.post("/auth/refresh", response_model=TokenPair)
@limiter.limit("30/minute")
def refresh(request: Request, body: RefreshIn, db: DB) -> TokenPair:
    """Swap a refresh token for a new pair. Each refresh token works once; reusing an old one
    signs the account out everywhere, because it means the token was copied."""
    now = datetime.now(UTC)
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(body.refresh_token))
    )
    if row is None:
        raise ApiError(401, "invalid_refresh_token", "Sign in again.")
    if row.revoked_at is not None:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == row.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        db.commit()
        raise ApiError(
            401,
            "refresh_token_reused",
            "This session was used somewhere else, so every session was signed out.",
        )
    if row.expires_at <= now:
        raise ApiError(401, "refresh_token_expired", "Your session expired. Sign in again.")
    user = db.get(User, row.user_id)
    if user is None:
        raise ApiError(401, "invalid_refresh_token", "Sign in again.")
    pair, new_row = _issue_tokens(db, user)
    row.revoked_at, row.replaced_by = now, new_row.id
    db.commit()
    return pair


@router.post("/auth/logout", status_code=204)
def logout(body: RefreshIn, db: DB) -> Response:
    """Sign this session out. Always succeeds, so it reveals nothing about the token."""
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(body.refresh_token))
    )
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.commit()
    return Response(status_code=204)


@router.get("/me", response_model=UserOut, tags=["account"])
def me(user: CurrentUser) -> User:
    """The signed-in account."""
    return user


@router.delete("/me", status_code=204, tags=["account"], responses={409: {"model": ErrorOut}})
def delete_me(user: CurrentUser, db: DB) -> Response:
    """Delete the account. Refused while you're the last owner of any Circle."""
    owners = (
        select(Membership.circle_id, func.count().label("n"))
        .where(Membership.role == Role.owner)
        .group_by(Membership.circle_id)
        .subquery()
    )
    last_owner = db.scalar(
        select(func.count())
        .select_from(Membership)
        .join(owners, owners.c.circle_id == Membership.circle_id)
        .where(Membership.user_id == user.id, Membership.role == Role.owner, owners.c.n == 1)
    )
    if last_owner:
        raise ApiError(
            409,
            "last_owner",
            "You're the only owner of a Circle. Give someone else ownership or delete "
            "the Circle first.",
        )
    db.delete(user)
    db.commit()
    return Response(status_code=204)
