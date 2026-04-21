"""Data models for stock image search results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StockImage:
    """Normalized stock image data from any provider (Pixabay, Pexels, etc.)."""

    id: str
    source: str  # "pixabay" | "pexels"
    page_url: str
    image_url: str
    preview_url: str
    width: int
    height: int
    tags: str
    photographer: str

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON output."""
        return {
            "id": self.id,
            "source": self.source,
            "page_url": self.page_url,
            "image_url": self.image_url,
            "preview_url": self.preview_url,
            "width": self.width,
            "height": self.height,
            "tags": self.tags,
            "photographer": self.photographer,
        }
