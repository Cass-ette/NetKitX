"""Marketplace models."""

import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class MarketplacePlugin(Base):
    """Marketplace plugin metadata."""

    __tablename__ = "marketplace_plugins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    homepage_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    repository_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    license: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    downloads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    versions: Mapped[list["MarketplaceVersion"]] = relationship(
        back_populates="plugin", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["MarketplaceReview"]] = relationship(
        back_populates="plugin", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_plugins_tags", "tags", postgresql_using="gin"),)


class MarketplaceVersion(Base):
    """Marketplace plugin version."""

    __tablename__ = "marketplace_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plugin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("marketplace_plugins.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    changelog: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    package_url: Mapped[str] = mapped_column(Text, nullable=False)
    package_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    package_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    min_netkitx_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    max_netkitx_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    published_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    yanked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    plugin: Mapped["MarketplacePlugin"] = relationship(back_populates="versions")
    dependencies: Mapped[list["MarketplaceDependency"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_versions_plugin", "plugin_id"),
        Index("idx_versions_plugin_version", "plugin_id", "version", unique=True),
    )


class MarketplaceDependency(Base):
    """Plugin dependency relationship."""

    __tablename__ = "marketplace_dependencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("marketplace_versions.id", ondelete="CASCADE"), nullable=False
    )
    depends_on_plugin: Mapped[str] = mapped_column(String(255), nullable=False)
    version_constraint: Mapped[str] = mapped_column(String(100), nullable=False)
    optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    version: Mapped["MarketplaceVersion"] = relationship(back_populates="dependencies")

    __table_args__ = (Index("idx_deps_version", "version_id"),)


class UserInstalledPlugin(Base):
    """User installed plugin record."""

    __tablename__ = "user_installed_plugins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plugin_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    installed_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_user_installed_user", "user_id"),
        Index("idx_user_installed_unique", "user_id", "plugin_name", unique=True),
    )


class MarketplaceReview(Base):
    """Plugin review and rating."""

    __tablename__ = "marketplace_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plugin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("marketplace_plugins.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now(), nullable=False)

    # Relationships
    plugin: Mapped["MarketplacePlugin"] = relationship(back_populates="reviews")

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_rating_range"),
        Index("idx_reviews_plugin", "plugin_id"),
        Index("idx_reviews_unique", "plugin_id", "user_id", unique=True),
    )


class MarketplaceReport(Base):
    """Plugin security report."""

    __tablename__ = "marketplace_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plugin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("marketplace_plugins.id", ondelete="CASCADE"), nullable=False
    )
    reporter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(50), nullable=False)  # malware, spam, copyright, other
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, reviewing, resolved, rejected
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now(), nullable=False)
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("idx_reports_plugin", "plugin_id"),
        Index("idx_reports_status", "status"),
    )

