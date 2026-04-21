"""Abstract base class for stock image providers."""

from abc import ABC, abstractmethod

from core.stock_image.models import StockImage


class StockImageProvider(ABC):
    """Abstract interface for stock image search providers.

    Implement this to add support for a new stock image provider
    (e.g., Pixabay, Pexels, Unsplash).
    """

    @abstractmethod
    def search(self, query: str, per_page: int = 5) -> list[StockImage]:
        """Search for images matching the query.

        Args:
            query: Search keywords (e.g. "frozen landscape glacier").
            per_page: Maximum number of results to return.

        Returns:
            List of StockImage results, up to per_page items.

        Raises:
            StockImageProviderError: If the API call fails.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier (e.g. 'pixabay', 'pexels')."""
        ...


class StockImageProviderError(Exception):
    """Raised when a stock image provider encounters an error."""

    pass
