from pydantic import BaseModel


class AISettingsUpdate(BaseModel):
    provider: str  # "claude" | "deepseek"
    api_key: str  # plaintext, encrypted on save
    model: str


class AISettingsResponse(BaseModel):
    provider: str
    api_key_masked: str  # e.g. "sk-...xxxx"
    model: str
    configured: bool = True

    model_config = {"from_attributes": True}


class AIAnalyzeRequest(BaseModel):
    task_id: int | None = None
    content: str = ""
    custom_prompt: str | None = None
    mode: str = "defense"  # "defense" | "offense"


class AIChatRequest(BaseModel):
    messages: list[dict[str, str]]  # [{role: "user", content: "..."}]
    mode: str = "defense"  # "defense" | "offense"
