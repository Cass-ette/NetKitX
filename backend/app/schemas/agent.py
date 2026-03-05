"""Agent mode schemas."""

from typing import Any

from pydantic import BaseModel, Field


class ConfirmAction(BaseModel):
    """Mode A confirmation payload."""

    approved: bool
    action: dict[str, Any]


class AgentRequest(BaseModel):
    """Request body for the agent endpoint."""

    messages: list[dict[str, str]]
    agent_mode: str = Field(pattern=r"^(semi_auto|full_auto|terminal)$")
    security_mode: str = "offense"
    lang: str = "en"
    max_turns: int = Field(default=0, ge=0)  # 0 = unlimited
    confirm_action: ConfirmAction | None = None
