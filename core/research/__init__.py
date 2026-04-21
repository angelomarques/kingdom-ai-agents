"""Web research domain port and models."""

from core.research.base import ResearchProviderError, WebResearchProvider
from core.research.models import ContentShape, ResearchRequest, ResearchResult, ResearchSource

__all__ = [
    "ContentShape",
    "ResearchProviderError",
    "ResearchRequest",
    "ResearchResult",
    "ResearchSource",
    "WebResearchProvider",
]
