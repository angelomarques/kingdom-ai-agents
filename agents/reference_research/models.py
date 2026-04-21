"""Models for the reference research agent."""

import re
from dataclasses import dataclass
from pathlib import Path

from core.research.models import ResearchSource


@dataclass(frozen=True)
class ReferenceResearchConfig:
    """Configuration for a reference research run."""

    theme: str
    output_filename: str | None = None
    output_path: Path | None = None

    def derive_output_basename(self) -> str:
        if self.output_filename:
            name = self.output_filename
            if not name.endswith(".json"):
                name += ".json"
            return name
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", self.theme.strip().lower()).strip("_")
        slug = slug[:80] or "reference_research"
        return f"{slug}.json"


@dataclass(frozen=True)
class ReferenceResearchResult:
    """Completed reference research output."""

    json_path: Path
    theme: str
    sources: tuple[ResearchSource, ...]
