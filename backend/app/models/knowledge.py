"""Agent session persistence & knowledge base models."""

import datetime

from typing import Optional

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    agent_mode: Mapped[str] = mapped_column(String(20))  # semi_auto|full_auto|terminal
    security_mode: Mapped[str] = mapped_column(String(20))  # offense|defense
    lang: Mapped[str] = mapped_column(String(10), default="en")
    total_turns: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|completed|failed
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[Optional[datetime.datetime]] = mapped_column(nullable=True)


class SessionTurn(Base):
    __tablename__ = "session_turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("agent_sessions.id", ondelete="CASCADE"), index=True
    )
    turn_number: Mapped[int] = mapped_column(default=0)
    role: Mapped[str] = mapped_column(String(20))  # user|assistant|action_result
    content: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    action_result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    action_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agent_sessions.id", ondelete="SET NULL"), nullable=True
    )
    scenario: Mapped[str] = mapped_column(Text, default="")
    target_type: Mapped[str] = mapped_column(String(50), default="other")
    vulnerability_type: Mapped[str] = mapped_column(String(50), default="other")
    tools_used: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    attack_chain: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str] = mapped_column(String(20), default="partial")
    key_findings: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

    __table_args__ = (Index("ix_knowledge_entries_session_id", "session_id"),)
