"""Prompt construction for content generation."""

from typing import Any

from app.ai.platform_strategy import PlatformStrategy
from app.domain.enums import Language
from app.schemas.briefs import ContentBrief


def build_system_instruction(
    strategy: PlatformStrategy,
    language: Language,
) -> str:
    """Build the system instruction combining platform strategy and language mandate."""
    platform_fragment = strategy.system_prompt_fragment()

    if language == Language.BENGALI:
        language_mandate = (
            "\n\nCRITICAL LANGUAGE REQUIREMENT:\n"
            "You MUST write ALL content — caption, hook, CTA, hashtags, "
            "media direction — entirely in native Bengali (বাংলা লিপি).\n"
            "Do NOT transliterate Bengali into English script.\n"
            "Do NOT mix English words unless they are universally recognised "
            "brand names or technical terms with no common Bengali equivalent.\n"
            "The output must read naturally to a native Bengali speaker."
        )
    elif language == Language.ENGLISH:
        language_mandate = (
            "\n\nLANGUAGE REQUIREMENT:\n"
            "Write ALL content — caption, hook, CTA, hashtags, "
            "media direction — entirely in English.\n"
            "Use clear, engaging, professional English appropriate for the target audience."
        )
    else:
        language_mandate = ""

    return f"{platform_fragment}{language_mandate}"


def build_generation_prompt(
    brief: ContentBrief,
    strategy: PlatformStrategy,
    *,
    previous_insights: list[dict[str, Any]] | None = None,
    rejection_reason: str | None = None,
) -> str:
    """Build the user prompt from a content brief and platform strategy."""
    rules = strategy.content_rules()

    sections = [
        f"## Content Brief",
        f"Title: {brief.title}",
        f"Genre: {brief.genre}",
        f"Language: {brief.language.value}",
        f"Target audience: {brief.audience}",
        f"Objective: {brief.objective}",
    ]

    if brief.key_themes:
        sections.append(f"Key themes: {', '.join(brief.key_themes)}")
    if brief.tone:
        sections.append(f"Tone: {brief.tone}")
    if brief.cta:
        sections.append(f"Preferred CTA: {brief.cta}")
    if brief.release_date:
        sections.append(f"Release date: {brief.release_date}")

    sections.append(f"\n## Platform Rules ({rules['platform']})")
    for key, value in rules.items():
        if key != "platform":
            sections.append(f"- {key.replace('_', ' ').title()}: {value}")

    if previous_insights:
        sections.append("\n## Previous Campaign Insights")
        sections.append(
            "Use these insights to improve this post. "
            "Do not repeat mistakes identified below."
        )
        for i, insight in enumerate(previous_insights, 1):
            summary = insight.get("summary", "No summary")
            sections.append(f"{i}. {summary}")

    if rejection_reason:
        sections.append("\n## Previous Rejection Feedback")
        sections.append(
            f"This post was previously rejected for the following reason:\n"
            f"{rejection_reason}\n"
            f"Address this feedback in the new version."
        )

    sections.append(
        "\n## Instructions"
        "\nGenerate a complete platform-ready post following the brief "
        "and platform rules above. Return structured JSON only."
    )

    return "\n".join(sections)
