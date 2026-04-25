"""Google Gemini LLM provider implementation."""

import logging
import os
import time
from collections.abc import Sequence

from google import genai
from google.genai import types

from core.llm.base import LLMProvider, LLMProviderError
from core.llm.models import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)

_TERMINAL_BATCH_STATES = frozenset(
    {
        "JOB_STATE_SUCCEEDED",
        "JOB_STATE_FAILED",
        "JOB_STATE_CANCELLED",
        "JOB_STATE_EXPIRED",
    }
)

_BATCH_POLL_INTERVAL_SEC = 5
_BATCH_POLL_MAX_SEC = 30 * 60


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
        # Inline batch jobs are only accepted on the Gemini Developer API path;
        # the Vertex client rejects `inlined_requests` at validation time.
        self._mldev_client = genai.Client(api_key=resolved_key, vertexai=True)
        self._model = model or self.DEFAULT_MODEL

    @property
    def default_model(self) -> str:
        return self._model

    @staticmethod
    def _batch_job_state_name(state) -> str:
        if state is None:
            return "UNKNOWN"
        return getattr(state, "name", str(state))

    def _inline_batch_request(self, request: LLMRequest) -> dict:
        """Build one inlined request entry for batches.create (Developer API)."""
        config_kwargs: dict = {}
        if request.temperature is not None:
            config_kwargs["temperature"] = request.temperature
        if request.system_instruction:
            config_kwargs["system_instruction"] = request.system_instruction

        entry: dict = {"contents": request.prompt}
        if config_kwargs:
            entry["config"] = types.GenerateContentConfig(**config_kwargs)
        return entry

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

    def generate_batch(self, requests: Sequence[LLMRequest]) -> list[LLMResponse]:
        """Run prompts as one Gemini Developer API inline batch job (async job + poll).
        TODO: Implement this.
        """
        if not requests:
            return []

        resolved_models = [r.model or self._model for r in requests]
        if len(set(resolved_models)) > 1:
            raise LLMProviderError(
                "generate_batch requires every LLMRequest to use the same model "
                f"(after applying the provider default); got {set(resolved_models)!r}."
            )
        model = resolved_models[0]

        src = [self._inline_batch_request(r) for r in requests]

        logger.info(
            "Submitting Gemini batch job (%d inlined requests) for model %r...",
            len(src),
            model,
        )
        try:
            job = self._mldev_client.batches.create(
                model=model,
                src=src,
                config={"display_name": "kingdom-ai-agents-llm-batch"},
            )
        except Exception as e:
            raise LLMProviderError(f"Gemini batch job creation failed: {e}") from e

        job_name = job.name
        deadline = time.monotonic() + _BATCH_POLL_MAX_SEC

        while time.monotonic() < deadline:
            try:
                job = self._mldev_client.batches.get(name=job_name)
            except Exception as e:
                raise LLMProviderError(
                    f"Gemini batch job status poll failed: {e}"
                ) from e

            state_name = self._batch_job_state_name(job.state)
            if state_name in _TERMINAL_BATCH_STATES:
                break
            logger.debug("Batch job %s state=%s; waiting...", job_name, state_name)
            time.sleep(_BATCH_POLL_INTERVAL_SEC)
        else:
            raise LLMProviderError(
                f"Gemini batch job {job_name!r} did not finish within {_BATCH_POLL_MAX_SEC}s."
            )

        state_name = self._batch_job_state_name(job.state)
        if state_name != "JOB_STATE_SUCCEEDED":
            err = getattr(job, "error", None)
            detail = f": {err}" if err else ""
            raise LLMProviderError(
                f"Gemini batch job ended with state {state_name}{detail}"
            )

        dest = job.dest
        if dest is None:
            raise LLMProviderError(
                "Gemini batch job succeeded but returned no output destination."
            )

        inlined = getattr(dest, "inlined_responses", None)
        if not inlined:
            fn = getattr(dest, "file_name", None)
            if fn:
                raise LLMProviderError(
                    "Gemini batch returned file-based results; only inline batch "
                    "responses are supported. "
                    f"(dest.file_name={fn!r})"
                )
            raise LLMProviderError(
                "Gemini batch job succeeded but inlined_responses is missing or empty."
            )

        if len(inlined) != len(requests):
            raise LLMProviderError(
                f"Gemini batch returned {len(inlined)} responses for {len(requests)} requests."
            )

        out: list[LLMResponse] = []
        for i, inline in enumerate(inlined):
            item_err = getattr(inline, "error", None)
            if item_err:
                raise LLMProviderError(f"Gemini batch item {i} failed: {item_err}")

            gen = getattr(inline, "response", None)
            if gen is None:
                raise LLMProviderError(f"Gemini batch item {i} has no response.")

            text = getattr(gen, "text", None)
            if not text:
                raise LLMProviderError(f"Gemini batch item {i} returned empty text.")

            prompt_tokens = None
            completion_tokens = None
            um = getattr(gen, "usage_metadata", None)
            if um is not None:
                prompt_tokens = getattr(um, "prompt_token_count", None)
                completion_tokens = getattr(um, "candidates_token_count", None)

            out.append(
                LLMResponse(
                    text=text,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
            )

        logger.info(
            "Gemini batch job %r completed with %d responses.",
            job_name,
            len(out),
        )
        return out
