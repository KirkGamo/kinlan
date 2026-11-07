"""Passwords (Argon2id), access tokens (JWT, HS256, 15 min) and opaque refresh tokens (30 days)."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=30)
ALGORITHM = "HS256"

_hasher = PasswordHash.recommended()  # Argon2id
# Verified when the email is unknown, so a wrong email takes as long as a wrong password.
_DUMMY_HASH = _hasher.hash("kinlan-timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


def create_access_token(user_id: uuid.UUID, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    claims = {"sub": str(user_id), "iat": now, "exp": now + ACCESS_TTL, "type": "access"}
    return jwt.encode(claims, get_settings().jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID:
    """Return the user id, or raise jwt.InvalidTokenError (expired, tampered, wrong type)."""
    claims = jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=[ALGORITHM],
        options={"require": ["sub", "exp"]},
    )
    if claims.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    try:
        return uuid.UUID(claims["sub"])
    except ValueError as exc:
        raise jwt.InvalidTokenError("bad subject") from exc


def new_opaque_token() -> str:
    """A random token for refresh, invite and agent secrets. Only its hash is stored."""
    return secrets.token_urlsafe(32)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# Invite codes: 8 characters from an alphabet without look-alikes (no 0/O, 1/I/L), shown as
# K7QM-2RXP. Only the SHA-256 of the normalised code is stored.
INVITE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def new_invite_code() -> str:
    raw = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def normalise_code(code: str) -> str:
    """Accept k7qm2rxp, K7QM-2RXP or ' k7qm 2rxp ' alike."""
    return "".join(ch for ch in code.upper() if ch.isalnum())
