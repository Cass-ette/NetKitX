"""Whitelist schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class WhitelistTargetCreate(BaseModel):
    target_type: Literal["domain", "ip", "cidr"]
    target_value: str
    declaration: bool = True
    notes: str | None = None

    @field_validator("declaration")
    @classmethod
    def check_declaration(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must declare that you have authorization for this target")
        return v


class WhitelistTargetResponse(BaseModel):
    id: int
    target_type: str
    target_value: str
    declaration: bool
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
