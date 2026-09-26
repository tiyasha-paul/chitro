"""Structured media-asset metadata stored in ``PlatformPost.media_spec``."""

from pydantic import BaseModel, Field


class MediaAssetSpec(BaseModel):
    """Portable metadata for an asset submitted to a channel adapter."""

    media_type: str = Field(..., description="Asset type, such as image or video")
    mime_type: str = Field(..., description="Asset MIME type")
    width: int = Field(..., gt=0, description="Asset width in pixels")
    height: int = Field(..., gt=0, description="Asset height in pixels")
    size_bytes: int = Field(..., gt=0, description="Asset size in bytes")
    asset_url: str | None = Field(default=None, description="Optional asset URL")
    storage_key: str | None = Field(default=None, description="Optional storage key")
