"""Authorized target whitelist model."""

import datetime

from sqlalchemy import Integer, String, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AuthorizedTarget(Base):
    __tablename__ = "authorized_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)  # domain | ip | cidr
    target_value: Mapped[str] = mapped_column(String(500), nullable=False)
    declaration: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "target_type", "target_value", name="uq_user_target"),
    )
