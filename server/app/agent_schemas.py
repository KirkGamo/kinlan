"""Bodies for the agent API (Section 4.3: Agent, Commands, the ingest payload and command
contracts)."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field, IPvAnyAddress

from app.models import CommandStatus, OutageCause, Target


def _mac(value: str) -> str:
    v = value.strip().lower().replace("-", ":")
    parts = v.split(":")
    if len(parts) != 6 or not all(
        len(p) == 2 and all(c in "0123456789abcdef" for c in p) for p in parts
    ):
        raise ValueError("not a MAC address like a4:5e:60:12:34:56")
    return v


Mac = Annotated[str, AfterValidator(_mac)]
Version = Annotated[str, Field(min_length=1, max_length=32, examples=["0.1.0"])]


class PairIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$", description="The 6-digit code from the app")
    hostname: str = Field(max_length=255)
    os: str = Field(max_length=80, examples=["Windows 11"])
    agent_version: Version
    network_cidr: str | None = Field(default=None, max_length=43, examples=["192.168.1.0/24"])


class PairOut(BaseModel):
    agent_id: uuid.UUID
    agent_token: str = Field(description="Store it encrypted; it's shown only once")
    site_id: uuid.UUID
    site_name: str


class NetInfo(BaseModel):
    local_ip: IPvAnyAddress | None = None
    cidr: str | None = Field(default=None, max_length=43)
    gateway: IPvAnyAddress | None = None


class SampleIn(BaseModel):
    ts: datetime
    target: Target
    ip: IPvAnyAddress
    rtt_ms: float | None = Field(default=None, ge=0, le=60_000)
    ok: bool


class DeviceIn(BaseModel):
    mac: Mac
    ip: IPvAnyAddress | None = None
    hostname: str | None = Field(default=None, max_length=255)
    vendor: str | None = Field(default=None, max_length=120)


class OutageIn(BaseModel):
    started_at: datetime
    ended_at: datetime | None = None
    cause: OutageCause = OutageCause.unknown


class PortFindingIn(BaseModel):
    mac: Mac
    port: int = Field(ge=1, le=65535)
    service: str = Field(max_length=40)


class IngestIn(BaseModel):
    batch_id: uuid.UUID = Field(description="Random per batch; a resent batch is stored once")
    agent_version: Version
    sent_at: datetime
    netinfo: NetInfo | None = None
    samples: list[SampleIn] = Field(default_factory=list, max_length=20_000)
    devices: list[DeviceIn] = Field(default_factory=list, max_length=2_000)
    outages: list[OutageIn] = Field(default_factory=list, max_length=500)
    port_findings: list[PortFindingIn] = Field(default_factory=list, max_length=2_000)


class IngestOut(BaseModel):
    status: Literal["stored", "duplicate"]
    samples: int = 0
    rejected_samples: int = Field(0, description="Stamped more than 5 min in the future")
    devices: int = 0
    new_devices: int = 0
    outages: int = 0
    port_findings: int = 0


CommandType = Literal["scan", "ping_test", "diagnose", "port_check"]


class CommandIn(BaseModel):
    type: CommandType
    params: dict[str, Any] = Field(default_factory=dict)


class CommandOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    type: str
    params: dict[str, Any]
    status: CommandStatus
    result: dict[str, Any] | None
    created_at: datetime
    finished_at: datetime | None


class CommandBatch(BaseModel):
    commands: list[CommandOut]


class CommandResultIn(BaseModel):
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = Field(default=None, max_length=500)
