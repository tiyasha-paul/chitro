"""Abstract LLM provider interface.

The application depends on this abstraction rather than directly on any
concrete LLM SDK, making the provider replaceable.
"""

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AIProviderError(Exception):
    """Raised when the underlying LLM provider returns an error."""


class AIStructuredOutputError(AIProviderError):
    """Raised when the LLM response cannot be parsed into the expected schema."""


class LLMProvider(ABC):
    """Abstract interface for a text-generation LLM provider."""

    @abstractmethod
    async def generate_structured(
        self,
        *,
        prompt: str,
        system_instruction: str,
        output_schema: type[T],
        temperature: float = 0.8,
    ) -> T:
        """Generate structured output conforming to a Pydantic schema.

        Args:
            prompt: The user prompt.
            system_instruction: System-level instruction for the model.
            output_schema: Pydantic model class defining the expected output.
            temperature: Sampling temperature (0.0 - 2.0).

        Returns:
            An instance of output_schema populated by the LLM response.

        Raises:
            AIProviderError: If the LLM call fails.
            AIStructuredOutputError: If the response cannot be parsed.
        """
        ...
