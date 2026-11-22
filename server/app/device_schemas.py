"""Bodies for the device endpoints (Section 4.3, Devices)."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models import DeviceType


class DeviceOwner(BaseModel):
    user_id: uuid.UUID
    display_name: str


class DeviceOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    display_name: str = Field(description="Custom name, else hostname, else manufacturer, else MAC")
    custom_name: str | None
    hostname: str | None
    vendor: str | None
    mac: str
    ip: str | None
    device_type: DeviceType
    owner: DeviceOwner | None
    trusted: bool
    baseline: bool = Field(description="Found by the first scan after pairing")
    needs_review: bool = Field(description="Joined after the baseline and nobody trusted it yet")
    online: bool
    first_seen_at: datetime
    last_seen_at: datetime
    open_risky_ports: int
    is_agent: bool = Field(
        False, description="The PC running this site's agent (matched by its hostname)"
    )


class DeviceList(BaseModel):
    items: list[DeviceOut]
    next_cursor: str | None = None


class PortFindingOut(BaseModel):
    port: int
    service: str
    info: bool = False  # a web admin page (80, 8080): shown, but not counted as a risk
    first_seen_at: datetime
    last_seen_at: datetime


class PingTestOut(BaseModel):
    id: uuid.UUID
    ts: datetime
    sent: int
    received: int
    loss_pct: float
    min_ms: float | None
    avg_ms: float | None
    max_ms: float | None
    jitter_ms: float | None


class DeviceDetail(DeviceOut):
    risky_ports: list[PortFindingOut]
    last_ping_test: PingTestOut | None


class PingTestList(BaseModel):
    items: list[PingTestOut]
    next_cursor: str | None = None


Name = Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]


class DevicePatch(BaseModel):
    """Only the fields you send change. Send `null` to clear a custom name or to make a device
    shared."""

    custom_name: Name | None = None
    device_type: DeviceType | None = None
    owner_user_id: uuid.UUID | None = None
    trusted: bool | None = None
