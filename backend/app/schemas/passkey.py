"""Passkey authentication schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


class PasskeyRegistrationBegin(BaseModel):
    """Request to begin passkey registration."""

    name: str | None = Field(None, max_length=100, description="Optional name for this passkey")


class PasskeyRegistrationComplete(BaseModel):
    """Complete passkey registration with credential data."""

    credential: dict = Field(
        ..., description="WebAuthn credential from navigator.credentials.create()"
    )
    name: str | None = Field(None, max_length=100, description="Optional name for this passkey")


class PasskeyLoginBegin(BaseModel):
    """Request to begin passkey login."""

    pass  # No fields needed, will return challenge for any registered passkey


class PasskeyLoginComplete(BaseModel):
    """Complete passkey login with assertion data."""

    credential: dict = Field(..., description="WebAuthn assertion from navigator.credentials.get()")


class PasskeyCredentialResponse(BaseModel):
    """Passkey credential information."""

    id: int
    name: str | None
    created_at: datetime
    last_used_at: datetime | None
    transports: list[str] | None

    class Config:
        from_attributes = True
