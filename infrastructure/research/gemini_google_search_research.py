"""Gemini + Google Search grounding implementation of WebResearchProvider."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from google import genai
from google.genai import types

from core.research.base import ResearchProviderError, WebResearchProvider
from core.research.models import (
    ContentShape,
    ResearchRequest,
    ResearchResult,
    ResearchSource,
)
from core.research.urls import normalize_http_url

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-2.5-flash"

_ALLOWED_SHAPES: frozenset[str] = frozenset({"list", "table", "data", "mixed"})


def _strip_markdown_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _parse_sources_json(text: str) -> list[dict[str, Any]]:
    cleaned = _strip_markdown_fences(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ResearchProviderError(f"Model returned invalid JSON: {e}") from e

    if isinstance(data, dict) and "sources" in data:
        sources = data["sources"]
    elif isinstance(data, list):
        sources = data
    else:
        raise ResearchProviderError(
            "Expected a JSON object with a 'sources' array or a top-level array."
        )

    if not isinstance(sources, list):
        raise ResearchProviderError("'sources' must be an array.")

    return sources


def _coerce_content_shape(value: Any) -> ContentShape:
    s = str(value or "").strip().lower()
    if s not in _ALLOWED_SHAPES:
        raise ResearchProviderError(
            f"Invalid content_shape {value!r}; expected one of {sorted(_ALLOWED_SHAPES)}."
        )
    return s  # type: ignore[return-value]


def _sources_from_payload(items: list[dict[str, Any]]) -> tuple[ResearchSource, ...]:
    out: list[ResearchSource] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ResearchProviderError(f"Source #{i + 1} is not an object.")
        url = str(item.get("url", "")).strip()
        title = str(item.get("title", "")).strip()
        rationale = str(item.get("rationale", "")).strip()
        shape = _coerce_content_shape(item.get("content_shape"))
        if not url:
            raise ResearchProviderError(f"Source #{i + 1} is missing a URL.")
        out.append(
            ResearchSource(
                url=url,
                title=title or url,
                content_shape=shape,
                rationale=rationale,
            )
        )
    return tuple(out)


def _evidence_urls_from_response(response: Any) -> tuple[str, ...]:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return ()
    gm = getattr(candidates[0], "grounding_metadata", None)
    if gm is None:
        return ()
    chunks = getattr(gm, "grounding_chunks", None) or []
    seen: set[str] = set()
    ordered: list[str] = []
    for ch in chunks:
        web = getattr(ch, "web", None)
        if web is None:
            continue
        uri = getattr(web, "uri", None)
        if not uri:
            continue
        normalized = normalize_http_url(str(uri))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


class GeminiGoogleSearchResearchProvider(WebResearchProvider):
    """Uses Gemini with the Google Search grounding tool and parses JSON sources."""

    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        resolved_key = api_key or os.getenv("GEMINI_API_KEY")
        if not resolved_key:
            raise ResearchProviderError(
                "Gemini API key not found. Set GEMINI_API_KEY or pass api_key."
            )
        self._client = genai.Client(api_key=resolved_key, vertexai=True)
        self._default_model = default_model or _DEFAULT_MODEL

    def find_sources(self, request: ResearchRequest) -> ResearchResult:
        model = request.model or self._default_model
        tool = types.Tool(google_search=types.GoogleSearch())
        config = types.GenerateContentConfig(
            system_instruction=request.system_instruction,
            tools=[tool],
            temperature=0.3,
        )

        logger.info("Calling Gemini with Google Search grounding (model=%s)...", model)
        try:
            response = self._client.models.generate_content(
                model=model,
                contents=request.user_prompt,
                config=config,
            )
        except Exception as e:
            raise ResearchProviderError(f"Gemini API call failed: {e}") from e

        text = getattr(response, "text", None) or ""
        if not str(text).strip():
            raise ResearchProviderError("Gemini returned an empty response.")

        items = _parse_sources_json(str(text))
        sources = _sources_from_payload(items)
        evidence_urls = _evidence_urls_from_response(response)

        return ResearchResult(
            theme=request.theme,
            sources=sources,
            evidence_urls=evidence_urls,
        )
