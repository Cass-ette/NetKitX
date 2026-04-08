from pydantic import BaseModel
from typing import Optional


class ProviderConfig(BaseModel):
    """Configuration for a single AI provider."""

    api_key: str = ""  # plaintext, encrypted on save
    api_key_masked: str = ""  # e.g. "sk-...xxxx"
    model: str = ""
    base_url: Optional[str] = None


class AISettingsUpdate(BaseModel):
    """Update request for AI settings."""

    provider: str  # "deepseek" | "glm" | "custom"
    # Provider-specific configs (only the one matching 'provider' needs api_key)
    deepseek: ProviderConfig
    glm: ProviderConfig
    custom: ProviderConfig


class AISettingsResponse(BaseModel):
    """Response for AI settings."""

    provider: str
    deepseek: ProviderConfig
    glm: ProviderConfig
    custom: ProviderConfig

    model_config = {"from_attributes": True}


class AIAnalyzeRequest(BaseModel):
    task_id: int | None = None
    content: str = ""
    custom_prompt: str | None = None
    mode: str = "defense"  # "defense" | "offense"
    lang: str = "en"  # UI locale, e.g. "zh-CN", "en", "ja"


class AIChatRequest(BaseModel):
    messages: list[dict[str, str]]  # [{role: "user", content: "..."}]
    mode: str = "defense"  # "defense" | "offense"
    lang: str = "en"  # UI locale
