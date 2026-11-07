"""Request and response bodies (Pydantic v2)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.models import Role

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


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorOut(BaseModel):
    error: ErrorDetail
