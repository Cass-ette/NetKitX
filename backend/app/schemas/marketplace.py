"""Marketplace schemas."""

import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MarketplacePluginBase(BaseModel):
    """Base marketplace plugin schema."""

    name: str = Field(..., max_length=255)
    display_name: str = Field(..., max_length=255)
    author: str = Field(..., max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    tags: Optional[list[str]] = None
    homepage_url: Optional[str] = None
    repository_url: Optional[str] = None
    license: Optional[str] = Field(None, max_length=50)


class MarketplacePluginCreate(MarketplacePluginBase):
    """Create marketplace plugin."""

    pass


class MarketplacePluginResponse(MarketplacePluginBase):
    """Marketplace plugin response."""

    id: int
    downloads: int
    rating: Optional[float] = None
    verified: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class MarketplaceVersionBase(BaseModel):
    """Base marketplace version schema."""

    version: str = Field(..., max_length=50)
    changelog: Optional[str] = None
    package_url: str
    package_hash: str = Field(..., max_length=64)
    package_size: Optional[int] = None
    min_netkitx_version: Optional[str] = Field(None, max_length=50)
    max_netkitx_version: Optional[str] = Field(None, max_length=50)


class MarketplaceVersionCreate(MarketplaceVersionBase):
    """Create marketplace version."""

    plugin_id: int


class MarketplaceVersionResponse(MarketplaceVersionBase):
    """Marketplace version response."""

    id: int
    plugin_id: int
    published_at: datetime.datetime
    yanked: bool

    class Config:
        from_attributes = True


class MarketplaceDependencyBase(BaseModel):
    """Base marketplace dependency schema."""

    depends_on_plugin: str = Field(..., max_length=255)
    version_constraint: str = Field(..., max_length=100)
    optional: bool = False


class MarketplaceDependencyCreate(MarketplaceDependencyBase):
    """Create marketplace dependency."""

    version_id: int


class MarketplaceDependencyResponse(MarketplaceDependencyBase):
    """Marketplace dependency response."""

    id: int
    version_id: int

    class Config:
        from_attributes = True


class MarketplacePluginDetail(MarketplacePluginResponse):
    """Detailed marketplace plugin with versions."""

    versions: list[MarketplaceVersionResponse] = []
    latest_version: Optional[str] = None


class MarketplaceSearchParams(BaseModel):
    """Search parameters."""

    query: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    verified_only: bool = False
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class MarketplaceInstallRequest(BaseModel):
    """Install plugin request."""

    plugin_name: str
    version: Optional[str] = None  # If None, install latest


class UserInstalledPluginResponse(BaseModel):
    """User installed plugin response."""

    id: int
    plugin_name: str
    version: str
    installed_at: datetime.datetime

    class Config:
        from_attributes = True


class MarketplaceReviewCreate(BaseModel):
    """Create review."""

    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class MarketplaceReviewResponse(MarketplaceReviewCreate):
    """Review response."""

    id: int
    plugin_id: int
    user_id: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True
