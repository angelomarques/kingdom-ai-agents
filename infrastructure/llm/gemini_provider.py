"""Google Gemini LLM provider implementation."""

import logging
import os

from google import genai
from google.genai import types

from core.llm.base import LLMProvider, LLMProviderError
from core.llm.models import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """LLM provider using Google Gemini models via the google-genai SDK."""

    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """Initialize the Gemini provider.

        Args:
            api_key: Gemini API key. Falls back to GEMINI_API_KEY env var.
            model: Default model to use. Falls back to DEFAULT_MODEL.
        """
        resolved_key = api_key or os.getenv("GEMINI_API_KEY")
        if not resolved_key:
            raise LLMProviderError(
                "Gemini API key not found. Set GEMINI_API_KEY environment variable "
                "or pass api_key to GeminiProvider."
            )

        self._client = genai.Client(api_key=resolved_key, vertexai=True)
        self._model = model or self.DEFAULT_MODEL

    @property
    def default_model(self) -> str:
        return self._model

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a prompt to Gemini and return the response."""
        model = request.model or self._model

        config_kwargs: dict = {}
        if request.temperature is not None:
            config_kwargs["temperature"] = request.temperature
        if request.system_instruction:
            config_kwargs["system_instruction"] = request.system_instruction

        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

        logger.info(f"Sending request to Gemini model '{model}'...")
        logger.debug(f"Prompt length: {len(request.prompt)} chars")

        try:
            response = self._client.models.generate_content(
                model=model,
                contents=request.prompt,
                config=config,
            )
        except Exception as e:
            raise LLMProviderError(f"Gemini API call failed: {e}") from e

        if not response.text:
            raise LLMProviderError("Gemini returned an empty response.")

        # Extract token usage if available
        prompt_tokens = None
        completion_tokens = None
        if response.usage_metadata:
            prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", None)
            completion_tokens = getattr(
                response.usage_metadata, "candidates_token_count", None
            )

        logger.info(
            f"Received response from Gemini ({prompt_tokens or '?'} prompt tokens, "
            f"{completion_tokens or '?'} completion tokens)"
        )

        return LLMResponse(
            text=response.text,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
