"""Rate limiting (slowapi; technical plan, Section 7). Off in the test environment so suites
can sign in freely; tests that check a limit switch it on (tests/test_rate_limits.py).

Every request is counted against its caller:

* a signed-in person by their user id (from the access token), so their phone and the web
  app share one budget, whatever network they're on;
* an agent by its token, so ingest is limited per agent, not per IP (a Circle's sites can
  share a NAT address);
* anyone else by IP address (sign-in, sign-up, pairing).

Limits: 120 requests a minute per caller on every route (:func:`default_limit`, an app-wide
dependency), plus tighter ones some routes set with ``@limiter.limit``: ingest 30 a minute per
agent; sign-in, sign-up, pairing and reports lower. slowapi's own middleware isn't used: it
can't see routes that FastAPI groups under included routers, so it would exempt them all.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from limits import parse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.errors import error_body
from app.security import decode_access_token, sha256_hex

DEFAULT_LIMIT = "120/minute"
INGEST_LIMIT = "30/minute"
_DEFAULT = parse(DEFAULT_LIMIT)
NOT_LIMITED = {"/healthz"}  # Render's health checks and the uptime monitor


def caller_key(request: Request) -> str:
    """Who to count this request against: the person, the agent, or the IP address."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            return f"user:{decode_access_token(token)}"
        except Exception:  # not an access token: an agent token (or a bad one)
            return f"token:{sha256_hex(token)[:32]}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=caller_key, enabled=get_settings().env != "test")


class TooManyRequests(Exception):
    pass


def default_limit(request: Request) -> None:
    """Every route: 120 requests a minute per caller (a FastAPI dependency on the app)."""
    if not limiter.enabled or request.url.path in NOT_LIMITED:
        return
    if not limiter.limiter.hit(_DEFAULT, "default", caller_key(request)):
        raise TooManyRequests


def _too_many_response() -> JSONResponse:
    return JSONResponse(
        error_body("rate_limited", "Too many requests. Wait a minute and try again."),
        status_code=429,
        headers={"Retry-After": "60"},
    )


def install_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _route_limit(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        return _too_many_response()

    @app.exception_handler(TooManyRequests)
    async def _default_limit(_: Request, exc: TooManyRequests) -> JSONResponse:
        return _too_many_response()
