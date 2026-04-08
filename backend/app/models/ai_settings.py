import datetime

from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AISettings(Base):
    __tablename__ = "ai_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)

    # Current active provider
    provider: Mapped[str] = mapped_column(String(20), default="deepseek")  # "deepseek" | "glm" | "custom"

    # DeepSeek settings
    deepseek_api_key_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deepseek_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="deepseek-chat")

    # GLM settings
    glm_api_key_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    glm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="glm-4-flash")

    # Custom settings
    custom_api_key_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    custom_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    custom_base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, default=None)

    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
