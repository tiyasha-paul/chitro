"""Gemini LLM provider implementation using google-genai SDK."""

import json
import logging
from typing import TypeVar

from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel, ValidationError

from app.ai.provider import AIProviderError, AIStructuredOutputError, LLMProvider
from app.config import settings

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class GeminiProvider(LLMProvider):
    """Gemini provider using the google-genai SDK."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._model = model or settings.GEMINI_MODEL
        if not self._api_key:
            raise AIProviderError("GEMINI_API_KEY is not configured")
        self._client = genai.Client(api_key=self._api_key)

    async def generate_structured(
        self,
        *,
        prompt: str,
        system_instruction: str,
        output_schema: type[T],
        temperature: float = 0.8,
    ) -> T:
        """Generate structured output via Gemini."""
        config = genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=output_schema,
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            logger.error("Gemini API call failed: %s", exc)
            raise AIProviderError(f"Gemini API error: {exc}") from exc

        raw_text = response.text
        if not raw_text:
            raise AIStructuredOutputError("Gemini returned an empty response")

        try:
            data = json.loads(raw_text)
            return output_schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.error(
                "Failed to parse Gemini response into %s: %s",
                output_schema.__name__,
                exc,
            )
            raise AIStructuredOutputError(
                f"Cannot parse response into {output_schema.__name__}: {exc}"
            ) from exc
