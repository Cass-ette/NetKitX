from pydantic import BaseModel


class SessionCreate(BaseModel):
    plugin_name: str
    params: dict = {}


class SessionResponse(BaseModel):
    session_id: str
    plugin_name: str
    user_id: int
    created_at: str
    last_active: str


class SessionMessage(BaseModel):
    type: str = "message"
    data: dict = {}
