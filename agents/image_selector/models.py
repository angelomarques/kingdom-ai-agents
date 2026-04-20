"""Data models for the Image Selector agent."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ImageItem:
    """A single selectable image."""

    description: str
    tags: list[str]
    url: str


@dataclass(frozen=True)
class Slide:
    """A slide containing a set of images to choose from."""

    title: str
    description: str
    images: list[ImageItem]


@dataclass(frozen=True)
class SelectorConfig:
    """Configuration for an image selection session."""

    input_path: Path
    output_path: Path


@dataclass(frozen=True)
class ImageSelection:
    """A single selection made by the user."""

    slide_index: int
    slide_title: str
    selected_image: ImageItem


@dataclass(frozen=True)
class SelectorResult:
    """Complete result of an image selection session."""

    selections: list[ImageSelection] = field(default_factory=list)
    skipped_slides: list[int] = field(default_factory=list)
    total_slides: int = 0
    output_path: Path | None = None
