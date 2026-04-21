"""Reference research agent — finds five list/table/data-friendly source URLs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import urlparse

from core.research.base import ResearchProviderError, WebResearchProvider
from core.research.models import ResearchRequest, ResearchResult, ResearchSource
from core.research.urls import normalize_http_url

from agents.reference_research.models import ReferenceResearchConfig, ReferenceResearchResult
from agents.reference_research.prompts import (
    SYSTEM_INSTRUCTION,
    build_retry_user_prompt,
    build_user_prompt,
)

logger = logging.getLogger(__name__)

_EXPECTED_COUNT = 5


class ReferenceResearchAgent:
    """Orchestrates web research and writes a JSON file of source references."""

    def __init__(
        self,
        research_provider: WebResearchProvider,
        output_dir: Path,
    ):
        self._research = research_provider
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, config: ReferenceResearchConfig) -> ReferenceResearchResult:
        logger.info("%s", "=" * 60)
        logger.info("Reference Research Agent")
        logger.info("Theme: %s", config.theme)
        logger.info("%s", "=" * 60)

        result = self._call_with_optional_retry(config.theme)

        self._validate_sources(result)

        payload = self._build_output_json(config.theme, result.sources)
        if config.output_path is not None:
            json_path = config.output_path.expanduser().resolve()
            json_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            json_path = (self._output_dir / config.derive_output_basename()).resolve()
        json_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info("Wrote %s", json_path)
        return ReferenceResearchResult(
            json_path=json_path,
            theme=config.theme,
            sources=result.sources,
        )

    def _call_with_optional_retry(self, theme: str) -> ResearchResult:
        req = ResearchRequest(
            theme=theme,
            user_prompt=build_user_prompt(theme),
            system_instruction=SYSTEM_INSTRUCTION,
        )
        result = self._research.find_sources(req)

        if len(result.sources) < _EXPECTED_COUNT:
            logger.warning(
                "First attempt returned %s sources (< %s); retrying once with broader prompt.",
                len(result.sources),
                _EXPECTED_COUNT,
            )
            retry_req = ResearchRequest(
                theme=theme,
                user_prompt=build_retry_user_prompt(theme),
                system_instruction=SYSTEM_INSTRUCTION,
            )
            result = self._research.find_sources(retry_req)

        return result

    def _validate_sources(self, result: ResearchResult) -> None:
        if len(result.sources) != _EXPECTED_COUNT:
            raise ResearchProviderError(
                f"Expected exactly {_EXPECTED_COUNT} sources, got {len(result.sources)}."
            )

        normalized: list[str] = []
        for s in result.sources:
            parsed = urlparse(s.url)
            if parsed.scheme != "https":
                raise ResearchProviderError(
                    f"All URLs must use https; got scheme {parsed.scheme!r} for {s.url!r}."
                )
            n = normalize_http_url(s.url)
            normalized.append(n)

        if len(set(normalized)) != _EXPECTED_COUNT:
            raise ResearchProviderError("Sources must contain five distinct URLs.")

    def _build_output_json(self, theme: str, sources: tuple[ResearchSource, ...]) -> dict:
        return {
            "theme": theme,
            "sources": [
                {
                    "url": s.url,
                    "title": s.title,
                    "content_shape": s.content_shape,
                    "rationale": s.rationale,
                }
                for s in sources
            ],
        }
