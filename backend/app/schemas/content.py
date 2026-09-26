"""Generated content output schemas."""

from pydantic import BaseModel, Field

from app.domain.enums import Language, Platform


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
