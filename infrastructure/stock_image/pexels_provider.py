"""Pexels stock image provider implementation."""

import logging
import os

import httpx

from core.stock_image.base import StockImageProvider, StockImageProviderError
from core.stock_image.models import StockImage

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.pexels.com/v1/search"


class PexelsProvider(StockImageProvider):
    """Stock image provider using the Pexels API.

    API docs: https://www.pexels.com/api/documentation/
    """

    def __init__(self, api_key: str | None = None):
        """Initialize the Pexels provider.

        Args:
            api_key: Pexels API key. Falls back to PEXELS_API_KEY env var.
        """
        resolved_key = api_key or os.getenv("PEXELS_API_KEY")
        if not resolved_key:
            raise StockImageProviderError(
                "Pexels API key not found. Set PEXELS_API_KEY environment variable "
                "or pass api_key to PexelsProvider."
            )
        self._api_key = resolved_key

    @property
    def provider_name(self) -> str:
        return "pexels"

    def search(self, query: str, per_page: int = 5) -> list[StockImage]:
        """Search Pexels for photos matching the query.

        Args:
            query: Search keywords.
            per_page: Maximum number of results (default 5, max 80).

        Returns:
            List of StockImage results from Pexels.
        """
        params = {
            "query": query,
            "per_page": min(per_page, 80),
        }
        headers = {
            "Authorization": self._api_key,
        }

        logger.info("Pexels search: %r (per_page=%d)", query, per_page)

        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(_BASE_URL, params=params, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise StockImageProviderError(
                f"Pexels API returned HTTP {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise StockImageProviderError(
                f"Pexels API request failed: {e}"
            ) from e

        data = response.json()
        photos = data.get("photos", [])

        logger.info("Pexels returned %d photos (total: %s)", len(photos), data.get("total_results"))

        results: list[StockImage] = []
        for photo in photos:
            src = photo.get("src", {})
            results.append(
                StockImage(
                    id=str(photo["id"]),
                    source="pexels",
                    page_url=photo.get("url", ""),
                    image_url=src.get("large", ""),
                    preview_url=src.get("medium", ""),
                    width=photo.get("width", 0),
                    height=photo.get("height", 0),
                    tags=photo.get("alt", ""),
                    photographer=photo.get("photographer", ""),
                )
            )

        return results
