"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

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

    @abstractmethod
    def generate_batch(self, requests: Sequence[LLMRequest]) -> list[LLMResponse]:
        """Run multiple LLM requests as a single batch job.

        Implementations should preserve order: the i-th response corresponds
        to the i-th request. An empty ``requests`` sequence must yield an empty list.

        Args:
            requests: Prompts and options for each item in the batch.

        Returns:
            One ``LLMResponse`` per input request, in the same order.

        Raises:
            LLMProviderError: If the batch job fails or any item has no usable text.
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
