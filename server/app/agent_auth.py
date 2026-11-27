"""How agents talk to the API: bearer-token auth, version checks and gzip request bodies."""

import gzip
import io
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, Request, Response
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.deps import DB
from app.errors import ApiError
from app.models import Agent
from app.security import sha256_hex

MIN_AGENT_VERSION = (0, 1, 0)
# After decompression. The largest real batch is about 190 KB (500 backlog rows with scans
# among the samples) and one scan of a full /22 is 184 KB, so 1 MB leaves room; anything bigger
# gets 413 and the agent sends it again in halves (plan, Section 7; issue #93).
MAX_BODY_BYTES = 1024 * 1024

_bearer = HTTPBearer(auto_error=False, description="The agent token from POST /agent/pair")


def parse_version(text: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in text.split("+")[0].split("-")[0].split("."))
    except ValueError:
        return (0,)


def check_version(agent_version: str) -> None:
    """Agents older than the minimum get 426 Upgrade Required."""
    if parse_version(agent_version) < MIN_AGENT_VERSION:
        minimum = ".".join(map(str, MIN_AGENT_VERSION))
        raise ApiError(
            426, "agent_too_old", f"Agent {agent_version} is too old. Install {minimum} or newer."
        )


def current_agent(
    db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> Agent:
    """The calling agent. Every authenticated call also counts as a heartbeat."""
    if creds is None:
        raise ApiError(401, "not_authenticated", "Missing agent token.")
    agent = db.scalar(select(Agent).where(Agent.token_hash == sha256_hex(creds.credentials)))
    if agent is None or agent.revoked_at is not None:
        raise ApiError(
            401, "invalid_agent_token", "This agent isn't paired. Run `kinlan-agent pair`."
        )
    agent.last_seen_at = datetime.now(UTC)
    return agent


CurrentAgent = Annotated[Agent, Depends(current_agent)]


class GzipRequest(Request):
    """Accepts `Content-Encoding: gzip` bodies, as the agent sends its batches compressed."""

    async def body(self) -> bytes:
        if not hasattr(self, "_body"):
            raw = await super().body()
            if "gzip" in self.headers.get("content-encoding", ""):
                try:
                    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as f:
                        raw = f.read(MAX_BODY_BYTES + 1)
                except OSError as exc:
                    raise ApiError(400, "bad_gzip", "The request body isn't valid gzip.") from exc
            if len(raw) > MAX_BODY_BYTES:
                raise ApiError(413, "body_too_large", "Send smaller batches (at most 1 MB).")
            self._body = raw
        return self._body


class GzipRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Any]:
        handler = super().get_route_handler()

        async def gzip_handler(request: Request) -> Response:
            request = GzipRequest(request.scope, request.receive)
            # Read (and size-check) the body here: an error raised while FastAPI parses it
            # would reach the agent as a generic 400, and only a 413 makes it send halves.
            await request.body()
            return await handler(request)

        return gzip_handler
