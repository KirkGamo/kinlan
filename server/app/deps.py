"""Shared FastAPI dependencies."""

from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.models import User
from app.security import decode_access_token

DB = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False, description="Access token from /auth/login")


def current_user(
    db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> User:
    """The signed-in user, from a valid access token."""
    if creds is None:
        raise ApiError(401, "not_authenticated", "Sign in to continue.")
    try:
        user_id = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise ApiError(
            401, "token_expired", "Your session expired. Refresh it or sign in again."
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise ApiError(401, "invalid_token", "That access token isn't valid.") from exc
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(401, "invalid_token", "That account no longer exists.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
