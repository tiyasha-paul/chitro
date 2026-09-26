#!/usr/bin/env python3
"""Milestone 2 Real Gemini Smoke Test.

Performs a live call using the configured .env (without exposing secrets).
Validates that structured Bengali output is returned conforming to
GeneratedInstagramPost.
"""

import asyncio
import sys

from app.ai.gemini import GeminiProvider
from app.config import settings
from app.domain.enums import Language, Platform
from app.schemas.briefs import ContentBrief
from app.services.generation import GenerationService


async def run_smoke_test():
    if not settings.GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY is not set in .env")
        sys.exit(1)

    print(f"Model configured: {settings.GEMINI_MODEL}")
    print(f"API key configured: Yes (length: {len(settings.GEMINI_API_KEY)})")

    provider = GeminiProvider()
    service = GenerationService(provider=provider)

    brief = ContentBrief(
        title="নিখোঁজ (Nikhoj)",
        genre="Psychological Thriller",
        language=Language.BENGALI,
        audience="Bengali thriller enthusiasts and OTT subscribers aged 22-40",
        objective="Drive trailer engagement and premier hype",
        key_themes=["রহস্যজনক নিখোঁজ", "সত্যের অনুসন্ধান", "অন্ধকার অতীত"],
        tone="Suspenseful, gripping, dramatic",
        cta="এখনই হইচই অ্যাপে টিজারটি দেখুন",
        release_date="এই শুক্রবার",
    )

    print("\nSending structured generation request to Gemini...")
    result = await service.generate_post(brief=brief, platform=Platform.INSTAGRAM)

    print("\n" + "=" * 50)
    print("GEMINI SMOKE TEST: SUCCESS")
    print("=" * 50)
    print(f"Platform: {result.platform.value}")
    print(f"Language: {result.language.value}")
    print(f"Hook: {result.hook}")
    print(f"\nCaption:\n{result.caption}")
    print(f"\nHashtags ({len(result.hashtags)}): {' '.join(result.hashtags)}")
    print(f"\nCTA: {result.cta}")
    print(f"\nMedia Direction:")
    print(f"  Description: {result.media_direction.description}")
    print(f"  Style: {result.media_direction.style}")
    print(f"  Mood: {result.media_direction.mood}")
    print(f"  Aspect Ratio: {result.media_direction.aspect_ratio}")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
