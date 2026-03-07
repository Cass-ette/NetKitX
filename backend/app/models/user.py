import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(20), default="user")  # admin | user
    github_id: Mapped[Optional[int]] = mapped_column(unique=True, nullable=True, default=None)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, default=None)
    max_concurrent_tasks: Mapped[int] = mapped_column(Integer, default=5)
    max_daily_tasks: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
