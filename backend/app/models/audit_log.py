"""Audit log model for tracking admin actions."""

import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    username: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(50), index=True)
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(100), default=None)
    details: Mapped[dict | None] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now(), index=True)
