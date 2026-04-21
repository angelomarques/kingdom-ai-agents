"""Data models for web research (domain layer)."""

from dataclasses import dataclass
from typing import Literal


ContentShape = Literal["list", "table", "data", "mixed"]


@dataclass(frozen=True)
class ResearchRequest:
    """Input for a web research job.

    Prompts are supplied by the application layer so infrastructure stays decoupled
    from agent-specific wording while the domain keeps a single request shape.
    """

    theme: str
    user_prompt: str
    system_instruction: str
    model: str | None = None


@dataclass(frozen=True)
class ResearchSource:
    """One curated page suggested for list/table/data-style content."""

    url: str
    title: str
    content_shape: ContentShape
    rationale: str


@dataclass(frozen=True)
class ResearchResult:
    """Output of a web research job.

    evidence_urls: URLs returned by the retrieval/grounding layer (e.g. Google Search
    grounding chunks). Used by the application layer to verify model-suggested URLs.
    """

    theme: str
    sources: tuple[ResearchSource, ...]
    evidence_urls: tuple[str, ...]
