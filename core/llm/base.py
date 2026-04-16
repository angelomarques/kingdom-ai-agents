"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod

from core.llm.models import LLMRequest, LLMResponse


class LLMProvider(ABC):
    """Abstract interface for language model providers.

    Implement this to add support for a new LLM provider
    (e.g., Gemini, Claude, OpenAI).
    """

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a prompt to the LLM and return the response.

        Args:
            request: The LLM request containing prompt, system instruction, etc.

        Returns:
            LLMResponse with the generated text and metadata.

        Raises:
            LLMProviderError: If the provider fails to generate a response.
        """
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model identifier for this provider."""
        ...


class LLMProviderError(Exception):
    """Raised when an LLM provider encounters an error."""

    pass
