"""Abstract web research provider (domain port)."""

from abc import ABC, abstractmethod

from core.research.models import ResearchRequest, ResearchResult


class WebResearchProvider(ABC):
    """Port for finding authoritative web pages for a research theme."""

    @abstractmethod
    def find_sources(self, request: ResearchRequest) -> ResearchResult:
        """Return curated sources and retrieval evidence URLs.

        Args:
            request: Theme and optional model override.

        Returns:
            ResearchResult including suggested sources and evidence_urls from retrieval.

        Raises:
            ResearchProviderError: If the provider cannot complete the request.
        """
        raise NotImplementedError


class ResearchProviderError(Exception):
    """Raised when a web research provider fails."""
