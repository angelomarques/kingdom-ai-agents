"""Models for the stock image search agent."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SlideInput:
    """A single slide/topic from the input."""

    topic: str


@dataclass(frozen=True)
class StockImageSearchConfig:
    """Configuration for a stock image search run."""

    theme: str
    slides: tuple[SlideInput, ...]
    input_path: Path
    output_path: Path | None = None

    @classmethod
    def from_json(cls, path: Path, output_path: Path | None = None) -> StockImageSearchConfig:
        """Parse the input JSON file into a config.

        Expected JSON format:
        {
            "theme": "Top 10 Coldest Countries",
            "slides": [
                {"topic": "Antarctica — Coldest continent"},
                {"topic": "Russia — Oymyakon"}
            ]
        }
        """
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Input file not found: {resolved}")

        data = json.loads(resolved.read_text(encoding="utf-8"))

        theme = data.get("theme", "")
        if not theme:
            raise ValueError("Input JSON must contain a non-empty 'theme' field.")

        raw_slides = data.get("slides", [])
        if not raw_slides:
            raise ValueError("Input JSON must contain a non-empty 'slides' array.")

        slides = tuple(
            SlideInput(topic=s["topic"])
            for s in raw_slides
            if "topic" in s
        )

        if not slides:
            raise ValueError("No valid slides found. Each slide must have a 'topic' field.")

        return cls(
            theme=theme,
            slides=slides,
            input_path=resolved,
            output_path=output_path,
        )

    def derive_output_basename(self) -> str:
        """Generate an output filename from the theme."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", self.theme.strip().lower()).strip("_")
        slug = slug[:80] or "stock_images"
        return f"{slug}_images.json"


@dataclass(frozen=True)
class StockImageSearchResult:
    """Completed stock image search output."""

    json_path: Path
    total_slides: int
    images_per_slide: list[int] = field(default_factory=list)
