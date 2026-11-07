"""Request and response bodies (Pydantic v2)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.models import Role, SiteStatus

Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class RegisterIn(BaseModel):
    email: EmailStr
    password: Password
    display_name: Name

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    created_at: datetime


class CircleIn(BaseModel):
    name: Name


class CircleOut(BaseModel):
    id: uuid.UUID
    name: str
    role: Role = Field(description="Your role in this Circle")
    member_count: int
    site_count: int
    created_at: datetime


class CircleList(BaseModel):
    items: list[CircleOut]
    next_cursor: str | None = None


class MemberOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str
    role: Role
    joined_at: datetime


class MemberList(BaseModel):
    items: list[MemberOut]
    next_cursor: str | None = None


class RoleIn(BaseModel):
    role: Role


class InviteIn(BaseModel):
    role: Role = Role.viewer


class InviteOut(BaseModel):
    code: str = Field(description="Show this to the person you're inviting, e.g. K7QM-2RXP")
    role: Role
    expires_at: datetime


class AcceptIn(BaseModel):
    code: str = Field(min_length=8, max_length=12)


_TIMEZONES = available_timezones()


def _check_tz(v: str | None) -> str | None:
    if v is not None and v not in _TIMEZONES:
        raise ValueError("unknown time zone; use an IANA name such as Asia/Manila")
    return v


class SiteIn(BaseModel):
    name: Name
    timezone: str = "Asia/Manila"

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        return _check_tz(v)


class SitePatch(BaseModel):
    name: Name | None = None
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        return _check_tz(v)


class SiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    circle_id: uuid.UUID
    name: str
    timezone: str
    status: SiteStatus
    last_seen_at: datetime | None
    cidr: str | None
    gateway_ip: str | None
    created_at: datetime

    @field_validator("gateway_ip", mode="before")
    @classmethod
    def _ip_text(cls, v: object) -> str | None:
        return None if v is None else str(v)


class SiteList(BaseModel):
    items: list[SiteOut]
    next_cursor: str | None = None


class LatestSample(BaseModel):
    ts: datetime
    rtt_ms: float | None = Field(description="null when the ping got no reply")
    ok: bool


class DeductionOut(BaseModel):
    factor: str
    points: int
    reason: str
    detail: str


class SiteSummary(BaseModel):
    site_id: uuid.UUID
    status: SiteStatus
    last_seen_at: datetime | None
    score: int
    grade: str
    grade_summary: str
    deductions: list[DeductionOut]
    internet: LatestSample | None
    gateway: LatestSample | None
    devices_total: int
    devices_online: int
    needs_review: int = Field(description="Untrusted devices first seen after the baseline")
    open_alerts: int
    open_outage_since: datetime | None


class PairingCodeOut(BaseModel):
    code: str = Field(description="6 digits, typed into `kinlan-agent pair` on the PC")
    expires_at: datetime


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    type: str
    severity: Literal["info", "warning", "critical"]
    title: str
    body: str
    subject_ref: str | None
    created_at: datetime
    acked_at: datetime | None
    acked_by: uuid.UUID | None
    resolved_at: datetime | None


class AlertList(BaseModel):
    items: list[AlertOut]
    next_cursor: str | None = None


class AlertSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    latency_ms: float
    loss_pct: float
    offline_seconds: int
    notify_new_device: bool


class AlertSettingsPatch(BaseModel):
    latency_ms: float | None = Field(default=None, ge=20, le=2000)
    loss_pct: float | None = Field(default=None, ge=0.5, le=50)
    offline_seconds: int | None = Field(default=None, ge=60, le=3600)
    notify_new_device: bool | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorOut(BaseModel):
    error: ErrorDetail
