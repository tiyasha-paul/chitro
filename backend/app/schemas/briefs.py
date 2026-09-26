"""Content brief schema for generation requests."""

from pydantic import BaseModel, Field

from app.domain.enums import Language


class ContentBrief(BaseModel):
    """Input brief for content generation."""

    title: str = Field(..., description="Title of the show/film/content")
    genre: str = Field(..., description="Genre of the content")
    language: Language = Field(..., description="Target language for generation")
    audience: str = Field(..., description="Target audience description")
    objective: str = Field(..., description="Marketing objective")
    key_themes: list[str] = Field(
        default_factory=list, description="Key themes to highlight"
    )
    tone: str | None = Field(None, description="Desired tone of the post")
    cta: str | None = Field(None, description="Preferred call-to-action")
    release_date: str | None = Field(
        None, description="Release date or timing reference"
    )
