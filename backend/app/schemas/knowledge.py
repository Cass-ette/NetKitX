"""Pydantic schemas for agent sessions & knowledge."""

from datetime import datetime

from pydantic import BaseModel


class SessionTurnResponse(BaseModel):
    id: int
    session_id: int
    turn_number: int
    role: str
    content: str
    action: dict | list | None = None
    action_result: dict | list | None = None
    action_status: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentSessionResponse(BaseModel):
    id: int
    user_id: int
    title: str
    agent_mode: str
    security_mode: str
    lang: str
    total_turns: int
    status: str
    summary: str | None = None
    created_at: datetime
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentSessionDetail(AgentSessionResponse):
    turns: list[SessionTurnResponse] = []


class SessionListResponse(BaseModel):
    items: list[AgentSessionResponse]
    total: int


class KnowledgeEntryResponse(BaseModel):
    id: int
    user_id: int
    session_id: int | None = None
    scenario: str
    target_type: str
    vulnerability_type: str
    tools_used: list | None = None
    attack_chain: str
    outcome: str
    key_findings: str
    tags: list | None = None
    summary: str
    learning_report: str = ""
    extraction_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeListResponse(BaseModel):
    items: list[KnowledgeEntryResponse]
    total: int


class KnowledgeSearchRequest(BaseModel):
    query: str
    limit: int = 10


class KnowledgeSearchResult(BaseModel):
    knowledge: KnowledgeEntryResponse
    similarity: float


class KnowledgeSearchResponse(BaseModel):
    results: list[KnowledgeSearchResult]
