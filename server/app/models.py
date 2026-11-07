"""SQLAlchemy models: every table in docs/KinLAN_Technical_Plan.md, Section 5.2.

UUID primary keys unless noted; every time is timestamptz in UTC.
"""

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    """A native PostgreSQL enum that stores the lower-case values, not the member names."""
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _fk(target: str, *, nullable: bool = False, ondelete: str = "CASCADE") -> Mapped[Any]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey(target, ondelete=ondelete), nullable=nullable
    )


def _ts(*, nullable: bool = False, default: bool = False) -> Mapped[Any]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=nullable,
        default=utcnow if default else None,
        server_default=func.now() if default else None,
    )


# ---------------------------------------------------------------- enums


class Role(enum.StrEnum):
    owner = "owner"
    admin = "admin"
    viewer = "viewer"


class SiteStatus(enum.StrEnum):
    online = "online"
    degraded = "degraded"
    unreachable = "unreachable"
    pending = "pending"


class DeviceType(enum.StrEnum):
    router = "router"
    computer = "computer"
    laptop = "laptop"
    phone = "phone"
    tv = "tv"
    printer = "printer"
    unknown = "unknown"


class Target(enum.StrEnum):
    gateway = "gateway"
    internet = "internet"


class OutageCause(enum.StrEnum):
    isp = "isp"
    lan = "lan"
    unknown = "unknown"


class DetectedBy(enum.StrEnum):
    agent = "agent"
    server = "server"


class CommandStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    expired = "expired"


# One type per enum, shared by every column that uses it.
ROLE = _enum(Role, "role")
TARGET = _enum(Target, "ping_target")


# ---------------------------------------------------------------- people and access


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _id()
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lower-case
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = _ts(default=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = _fk("users.id")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # SHA-256 hex
    expires_at: Mapped[datetime] = _ts()
    revoked_at: Mapped[datetime | None] = _ts(nullable=True)
    replaced_by: Mapped[uuid.UUID | None] = _fk(
        "refresh_tokens.id", nullable=True, ondelete="SET NULL"
    )

    __table_args__ = (Index("ix_refresh_tokens_user_id", "user_id"),)


class Circle(Base):
    __tablename__ = "circles"

    id: Mapped[uuid.UUID] = _id()
    name: Mapped[str] = mapped_column(String(80))
    created_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True, ondelete="SET NULL")
    created_at: Mapped[datetime] = _ts(default=True)


class Membership(Base):
    __tablename__ = "memberships"

    circle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("circles.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[Role] = mapped_column(ROLE)
    joined_at: Mapped[datetime] = _ts(default=True)

    __table_args__ = (Index("ix_memberships_user_id", "user_id"),)


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = _id()
    circle_id: Mapped[uuid.UUID] = _fk("circles.id")
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[Role] = mapped_column(ROLE)
    expires_at: Mapped[datetime] = _ts()
    used_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True, ondelete="SET NULL")
    used_at: Mapped[datetime | None] = _ts(nullable=True)


# ---------------------------------------------------------------- sites and agents


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = _id()
    circle_id: Mapped[uuid.UUID] = _fk("circles.id")
    name: Mapped[str] = mapped_column(String(80))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Manila")
    status: Mapped[SiteStatus] = mapped_column(
        _enum(SiteStatus, "site_status"), default=SiteStatus.pending
    )
    last_seen_at: Mapped[datetime | None] = _ts(nullable=True)
    cidr: Mapped[str | None] = mapped_column(String(43))
    gateway_ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = _ts(default=True)

    __table_args__ = (Index("ix_sites_circle_id", "circle_id"),)


class AlertSettings(Base):
    __tablename__ = "alert_settings"

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True
    )
    latency_ms: Mapped[float] = mapped_column(Float, default=150.0)
    loss_pct: Mapped[float] = mapped_column(Float, default=5.0)
    offline_seconds: Mapped[int] = mapped_column(Integer, default=120)
    notify_new_device: Mapped[bool] = mapped_column(Boolean, default=True)


class PairingCode(Base):
    __tablename__ = "pairing_codes"

    id: Mapped[uuid.UUID] = _id()
    site_id: Mapped[uuid.UUID] = _fk("sites.id")
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = _ts()
    used_at: Mapped[datetime | None] = _ts(nullable=True)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = _id()
    site_id: Mapped[uuid.UUID] = _fk("sites.id")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    hostname: Mapped[str | None] = mapped_column(String(255))
    os: Mapped[str | None] = mapped_column(String(80))
    version: Mapped[str | None] = mapped_column(String(32))
    last_seen_at: Mapped[datetime | None] = _ts(nullable=True)
    revoked_at: Mapped[datetime | None] = _ts(nullable=True)


# ---------------------------------------------------------------- devices and measurements


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = _id()
    site_id: Mapped[uuid.UUID] = _fk("sites.id")
    mac: Mapped[str] = mapped_column(String(17))
    ip: Mapped[str | None] = mapped_column(INET)
    hostname: Mapped[str | None] = mapped_column(String(255))
    vendor: Mapped[str | None] = mapped_column(String(120))
    device_type: Mapped[DeviceType] = mapped_column(
        _enum(DeviceType, "device_type"), default=DeviceType.unknown
    )
    custom_name: Mapped[str | None] = mapped_column(String(80))
    owner_user_id: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True, ondelete="SET NULL")
    trusted: Mapped[bool] = mapped_column(Boolean, default=False)
    baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen_at: Mapped[datetime] = _ts(default=True)
    last_seen_at: Mapped[datetime] = _ts(default=True)
    online: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("site_id", "mac", name="uq_devices_site_id_mac"),)


class PingSample(Base):
    __tablename__ = "ping_samples"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    site_id: Mapped[uuid.UUID] = _fk("sites.id")
    target: Mapped[Target] = mapped_column(TARGET)
    ip: Mapped[str] = mapped_column(INET)
    ts: Mapped[datetime] = _ts()
    rtt_ms: Mapped[float | None] = mapped_column(Float)
    ok: Mapped[bool] = mapped_column(Boolean)


class PingHourly(Base):
    __tablename__ = "ping_hourly"

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True
    )
    target: Mapped[Target] = mapped_column(TARGET, primary_key=True)
    hour: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    avg_ms: Mapped[float | None] = mapped_column(Float)
    min_ms: Mapped[float | None] = mapped_column(Float)
    max_ms: Mapped[float | None] = mapped_column(Float)
    loss_pct: Mapped[float] = mapped_column(Float)
    samples: Mapped[int] = mapped_column(Integer)


class PingTest(Base):
    __tablename__ = "ping_tests"

    id: Mapped[uuid.UUID] = _id()
    device_id: Mapped[uuid.UUID] = _fk("devices.id")
    ts: Mapped[datetime] = _ts(default=True)
    sent: Mapped[int] = mapped_column(Integer)
    received: Mapped[int] = mapped_column(Integer)
    loss_pct: Mapped[float] = mapped_column(Float)
    min_ms: Mapped[float | None] = mapped_column(Float)
    avg_ms: Mapped[float | None] = mapped_column(Float)
    max_ms: Mapped[float | None] = mapped_column(Float)
    jitter_ms: Mapped[float | None] = mapped_column(Float)


class Outage(Base):
    __tablename__ = "outages"

    id: Mapped[uuid.UUID] = _id()
    site_id: Mapped[uuid.UUID] = _fk("sites.id")
    started_at: Mapped[datetime] = _ts()
    ended_at: Mapped[datetime | None] = _ts(nullable=True)
    cause: Mapped[OutageCause] = mapped_column(
        _enum(OutageCause, "outage_cause"), default=OutageCause.unknown
    )
    detected_by: Mapped[DetectedBy] = mapped_column(_enum(DetectedBy, "detected_by"))


class PortFinding(Base):
    __tablename__ = "port_findings"

    id: Mapped[uuid.UUID] = _id()
    device_id: Mapped[uuid.UUID] = _fk("devices.id")
    port: Mapped[int] = mapped_column(Integer)
    service: Mapped[str] = mapped_column(String(40))
    first_seen_at: Mapped[datetime] = _ts(default=True)
    last_seen_at: Mapped[datetime] = _ts(default=True)
    resolved_at: Mapped[datetime | None] = _ts(nullable=True)

    __table_args__ = (
        UniqueConstraint("device_id", "port", name="uq_port_findings_device_id_port"),
    )


# ---------------------------------------------------------------- commands, alerts, push, reports


class Command(Base):
    __tablename__ = "commands"

    id: Mapped[uuid.UUID] = _id()
    site_id: Mapped[uuid.UUID] = _fk("sites.id")
    type: Mapped[str] = mapped_column(String(20))  # scan, ping_test, diagnose, port_check
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[CommandStatus] = mapped_column(
        _enum(CommandStatus, "command_status"), default=CommandStatus.pending
    )
    requested_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True, ondelete="SET NULL")
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _ts(default=True)
    finished_at: Mapped[datetime | None] = _ts(nullable=True)

    __table_args__ = (Index("ix_commands_site_status", "site_id", "status"),)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = _id()
    site_id: Mapped[uuid.UUID] = _fk("sites.id")
    type: Mapped[str] = mapped_column(String(40))  # new_device, unreachable, back_online, ...
    severity: Mapped[str] = mapped_column(String(10))  # info, warning, critical
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    subject_ref: Mapped[str | None] = mapped_column(String(80))  # e.g. device id or outage id
    created_at: Mapped[datetime] = _ts(default=True)
    acked_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True, ondelete="SET NULL")
    acked_at: Mapped[datetime | None] = _ts(nullable=True)
    resolved_at: Mapped[datetime | None] = _ts(nullable=True)


class PushToken(Base):
    __tablename__ = "push_tokens"

    token: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[uuid.UUID] = _fk("users.id")
    platform: Mapped[str] = mapped_column(String(10))  # android, web
    created_at: Mapped[datetime] = _ts(default=True)
    last_used_at: Mapped[datetime | None] = _ts(nullable=True)


class IngestBatch(Base):
    """Stops a resent batch from being stored twice. Kept 2 days."""

    __tablename__ = "ingest_batches"

    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    agent_id: Mapped[uuid.UUID] = _fk("agents.id")
    received_at: Mapped[datetime] = _ts(default=True)


class Report(Base):
    """Deleted after 30 days by the retention job."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = _id()
    site_id: Mapped[uuid.UUID] = _fk("sites.id")
    requested_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True, ondelete="SET NULL")
    range_start: Mapped[datetime] = _ts()
    range_end: Mapped[datetime] = _ts()
    created_at: Mapped[datetime] = _ts(default=True)
    pdf: Mapped[bytes | None] = mapped_column(LargeBinary)


# Newest-first indexes for the time-series reads (declared after the classes exist).
Index("ix_ping_samples_site_target_ts", PingSample.site_id, PingSample.target, PingSample.ts.desc())
Index("ix_ping_tests_device_ts", PingTest.device_id, PingTest.ts.desc())
Index("ix_outages_site_started", Outage.site_id, Outage.started_at.desc())
Index("ix_alerts_site_created", Alert.site_id, Alert.created_at.desc())
