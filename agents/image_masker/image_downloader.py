"""Download a remote image into a Pillow Image (httpx, same pattern as image_selector)."""

import io
import logging

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; KingdomAIAgents/0.1; "
        "+https://github.com/) Python-httpx"
    ),
}


def fetch_image_from_url(url: str, timeout: float = 30.0) -> Image.Image:
    """GET the URL and decode as an image; returns a loaded copy (caller owns)."""
    logger.debug("Fetching image: %s", url)
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers=_DEFAULT_HEADERS,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
    img = Image.open(io.BytesIO(response.content))
    return img.copy()
