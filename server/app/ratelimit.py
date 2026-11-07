"""Rate limiting (slowapi). Off in the test environment so suites can sign in freely."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.errors import error_body

limiter = Limiter(key_func=get_remote_address, enabled=get_settings().env != "test")


def install_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _too_many(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            error_body("rate_limited", "Too many attempts. Wait a minute and try again."),
            status_code=429,
        )
