"""Generated content output schemas."""

from pydantic import BaseModel, Field

from app.domain.enums import Language, Platform

class GeneratedMediaAsset(BaseModel):
    """Media metadata that may be returned by the LLM."""

    media_type: str = Field(..., description="Asset type, such as image or video")
    mime_type: str = Field(..., description="Asset MIME type")
    width: int = Field(..., description="Asset width in pixels")
    height: int = Field(..., description="Asset height in pixels")
    size_bytes: int = Field(..., description="Asset size in bytes")
    asset_url: str | None = Field(default=None, description="Optional asset URL")
    storage_key: str | None = Field(default=None, description="Optional storage key")

class MediaDirection(BaseModel):
    """AI-generated media/visual direction for accompanying imagery."""

    description: str = Field(..., description="Visual description for the post image")
    style: str = Field(..., description="Art/photo style suggestion")
    mood: str = Field(..., description="Mood/atmosphere of the visual")
    aspect_ratio: str = Field(
        default="1:1", description="Recommended aspect ratio"
    )


class GeneratedInstagramPost(BaseModel):
    """Structured output from AI generation for an Instagram post."""

    platform: Platform = Field(default=Platform.INSTAGRAM)
    language: Language = Field(..., description="Language of the generated content")
    hook: str = Field(..., description="Attention-grabbing opening line")
    caption: str = Field(..., description="Full Instagram caption")
    hashtags: list[str] = Field(..., description="List of hashtags")
    cta: str = Field(..., description="Call-to-action text")
    media_direction: MediaDirection = Field(
        ..., description="Visual/media direction for the post"
    )
    media_asset: GeneratedMediaAsset | None = Field(
    default=None,
    description="Optional concrete asset metadata when an asset is available",
    )