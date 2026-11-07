"""FastAPI application: app factory, middleware and routes."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.errors import install_error_handlers
from app.ratelimit import install_rate_limiting
from app.routers import agent, alerts, auth, circles, commands, sites

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Run the scheduled jobs alongside the API (off in tests and when RUN_JOBS=false)."""
    settings = get_settings()
    scheduler = None
    if settings.run_jobs and settings.env != "test":
        from app.jobs import start_scheduler

        scheduler = start_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    """Build the FastAPI app. Routers for each API group are added here as they're written."""
    settings = get_settings()
    app = FastAPI(
        title="KinLAN API",
        version=__version__,
        description="Cloud API for KinLAN agents and the KinLAN app.",
        lifespan=lifespan,
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
    app.include_router(sites.router, prefix=API_PREFIX)
    app.include_router(commands.router, prefix=API_PREFIX)
    app.include_router(alerts.router, prefix=API_PREFIX)
    app.include_router(agent.router, prefix=API_PREFIX)

    @app.get("/healthz", tags=["system"])
    def healthz() -> dict[str, str]:
        """Liveness check used by Render and the uptime monitor."""
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
