"""FastAPI application: app factory, middleware and routes."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.errors import install_error_handlers
from app.ratelimit import install_rate_limiting
from app.routers import auth, circles

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    """Build the FastAPI app. Routers for each API group are added here as they're written."""
    settings = get_settings()
    app = FastAPI(
        title="KinLAN API",
        version=__version__,
        description="Cloud API for KinLAN agents and the KinLAN app.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_error_handlers(app)
    install_rate_limiting(app)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(circles.router, prefix=API_PREFIX)

    @app.get("/healthz", tags=["system"])
    def healthz() -> dict[str, str]:
        """Liveness check used by Render and the uptime monitor."""
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
