"""Tavily Search + LLM curation implementation of WebResearchProvider."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from tavily import TavilyClient

from core.llm.base import LLMProvider, LLMProviderError
from core.llm.models import LLMRequest
from core.research.base import ResearchProviderError, WebResearchProvider
from core.research.models import (
    ContentShape,
    ResearchRequest,
    ResearchResult,
    ResearchSource,
)
from core.research.urls import normalize_http_url

logger = logging.getLogger(__name__)

_SEARCH_MAX_RESULTS = 10
_EXPECTED_CURATED = 5

_ALLOWED_SHAPES: frozenset[str] = frozenset({"list", "table", "data", "mixed"})


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

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
        raise ResearchProviderError(f"LLM returned invalid JSON: {e}") from e

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
        return "mixed"  # type: ignore[return-value]
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


# ---------------------------------------------------------------------------
# Curation prompt builder
# ---------------------------------------------------------------------------

_CURATION_SYSTEM = """You are a research assistant helping creators make videos or articles that rely on structured facts: ranked lists, comparisons, tables, or bullet-point data.

You will receive a list of web search results (URL, title, snippet) for a given theme.

Rules:
- Return ONLY valid JSON (no markdown fences, no commentary).
- Select exactly five distinct https URLs from the provided search results.
- Prefer pages that visibly present facts as a numbered/bulleted list, table, dataset, or clearly scannable sections (not long prose essays without structure).
- Prefer reputable sources (government statistics, Wikipedia data pages, major encyclopedias, established news data desks, university references) when possible.
- Only select URLs that appear in the search results provided; do not invent URLs.
- The JSON shape must be:
  {"sources":[{"url":"...","title":"...","content_shape":"list|table|data|mixed","rationale":"..."}]}
- content_shape: use "table" if the main facts are in a table; "list" for ranked/bulleted lists; "data" for numeric/stat blocks or downloadable-style figures; "mixed" if both prose and structured blocks appear.
"""


def _build_curation_prompt(theme: str, search_results: list[dict[str, Any]]) -> str:
    results_block = "\n".join(
        f"{i + 1}. [{r.get('title', 'Untitled')}]({r.get('url', '')})\n"
        f"   Snippet: {r.get('content', 'N/A')}\n"
        f"   Relevance score: {r.get('score', 'N/A')}"
        for i, r in enumerate(search_results)
    )

    return f"""Theme / topic for the creator's content:

"{theme}"

Below are the web search results. Select the best 5 pages for structured-fact reference and return JSON only.

--- SEARCH RESULTS ---
{results_block}
--- END SEARCH RESULTS ---

Return JSON only, with this exact structure:
{{"sources":[{{"url":"https://...","title":"...","content_shape":"list|table|data|mixed","rationale":"..."}}, ...]}}

There must be exactly 5 objects in "sources", and all URLs must use https.
Only use URLs that appear in the search results above.
"""


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class TavilyResearchProvider(WebResearchProvider):
    """Uses Tavily Search API for web search and an LLM for curation/ranking."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        api_key: str | None = None,
    ):
        resolved_key = api_key or os.getenv("TAVILY_API_KEY")
        if not resolved_key:
            raise ResearchProviderError(
                "Tavily API key not found. Set TAVILY_API_KEY or pass api_key."
            )
        self._tavily = TavilyClient(api_key=resolved_key)
        self._llm = llm_provider

    def find_sources(self, request: ResearchRequest) -> ResearchResult:
        # Step 1: Search via Tavily
        search_results = self._tavily_search(request.theme)

        if len(search_results) < _EXPECTED_CURATED:
            logger.warning(
                "Tavily returned only %d results (need %d); retrying with broader query.",
                len(search_results),
                _EXPECTED_CURATED,
            )
            broader = f"{request.theme} list ranking comparison statistics"
            extra = self._tavily_search(broader)

            # Merge, deduplicate by URL
            seen_urls = {r["url"] for r in search_results}
            for r in extra:
                if r["url"] not in seen_urls:
                    search_results.append(r)
                    seen_urls.add(r["url"])

        if len(search_results) < _EXPECTED_CURATED:
            raise ResearchProviderError(
                f"Tavily returned only {len(search_results)} search results "
                f"(need at least {_EXPECTED_CURATED}). Try a different theme."
            )

        evidence_urls = tuple(
            normalize_http_url(r["url"]) for r in search_results if r.get("url")
        )

        # Step 2: Curate via LLM
        sources = self._curate_with_llm(request.theme, search_results)

        return ResearchResult(
            theme=request.theme,
            sources=sources,
            evidence_urls=evidence_urls,
        )

    def _tavily_search(self, query: str) -> list[dict[str, Any]]:
        logger.info("Calling Tavily Search API (query=%r)...", query)
        try:
            response = self._tavily.search(
                query=query,
                max_results=_SEARCH_MAX_RESULTS,
                search_depth="advanced",
            )
        except Exception as e:
            raise ResearchProviderError(f"Tavily API call failed: {e}") from e

        results = response.get("results", [])
        logger.info("Tavily returned %d results.", len(results))
        return results

    def _curate_with_llm(
        self, theme: str, search_results: list[dict[str, Any]]
    ) -> tuple[ResearchSource, ...]:
        prompt = _build_curation_prompt(theme, search_results)
        llm_request = LLMRequest(
            prompt=prompt,
            system_instruction=_CURATION_SYSTEM,
            temperature=0.3,
        )

        logger.info("Calling LLM to curate %d search results...", len(search_results))
        try:
            llm_response = self._llm.generate(llm_request)
        except LLMProviderError as e:
            raise ResearchProviderError(f"LLM curation failed: {e}") from e

        items = _parse_sources_json(llm_response.text)
        sources = _sources_from_payload(items)

        # Validate that curated URLs are a subset of search results
        search_url_set = {
            normalize_http_url(r["url"]) for r in search_results if r.get("url")
        }
        for s in sources:
            normalized = normalize_http_url(s.url)
            if normalized not in search_url_set:
                raise ResearchProviderError(
                    f"LLM suggested a URL not present in Tavily search results: "
                    f"{s.url!r}. Only URLs from search results are allowed."
                )

        return sources
