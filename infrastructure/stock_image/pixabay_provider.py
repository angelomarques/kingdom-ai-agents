"""Pixabay stock image provider implementation."""

import logging
import os

import httpx

from core.stock_image.base import StockImageProvider, StockImageProviderError
from core.stock_image.models import StockImage

logger = logging.getLogger(__name__)

_BASE_URL = "https://pixabay.com/api/"


class PixabayProvider(StockImageProvider):
    """Stock image provider using the Pixabay API.

    API docs: https://pixabay.com/api/docs/
    """

    def __init__(self, api_key: str | None = None):
        """Initialize the Pixabay provider.

        Args:
            api_key: Pixabay API key. Falls back to PIXABAY_API_KEY env var.
        """
        resolved_key = api_key or os.getenv("PIXABAY_API_KEY")
        if not resolved_key:
            raise StockImageProviderError(
                "Pixabay API key not found. Set PIXABAY_API_KEY environment variable "
                "or pass api_key to PixabayProvider."
            )
        self._api_key = resolved_key

    @property
    def provider_name(self) -> str:
        return "pixabay"

    def search(self, query: str, per_page: int = 5) -> list[StockImage]:
        """Search Pixabay for photos matching the query.

        Args:
            query: Search keywords.
            per_page: Maximum number of results (default 5, max 200).

        Returns:
            List of StockImage results from Pixabay.
        """
        params = {
            "key": self._api_key,
            "q": query,
            "per_page": min(per_page, 200),
            "image_type": "photo",
            "safesearch": "true",
        }

        logger.info("Pixabay search: %r (per_page=%d)", query, per_page)

        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(_BASE_URL, params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise StockImageProviderError(
                f"Pixabay API returned HTTP {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise StockImageProviderError(
                f"Pixabay API request failed: {e}"
            ) from e

        data = response.json()
        hits = data.get("hits", [])

        logger.info("Pixabay returned %d hits (total: %s)", len(hits), data.get("totalHits"))

        results: list[StockImage] = []
        for hit in hits:
            results.append(
                StockImage(
                    id=str(hit["id"]),
                    source="pixabay",
                    page_url=hit.get("pageURL", ""),
                    image_url=hit.get("webformatURL", ""),
                    preview_url=hit.get("previewURL", ""),
                    width=hit.get("webformatWidth", 0),
                    height=hit.get("webformatHeight", 0),
                    tags=hit.get("tags", ""),
                    photographer=hit.get("user", ""),
                )
            )

        return results
