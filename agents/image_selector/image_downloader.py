"""Image downloader — fetches images from URLs to a local cache."""

import hashlib
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Supported image extensions (fallback when URL has no extension)
_DEFAULT_EXT = ".jpg"


def _url_to_cache_filename(url: str) -> str:
    """Generate a deterministic cache filename from a URL."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]

    # Try to preserve the original extension
    path_part = url.split("?")[0]  # Strip query params
    suffix = Path(path_part).suffix.lower()
    if suffix not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
        suffix = _DEFAULT_EXT

    return f"{url_hash}{suffix}"


def download_image(url: str, cache_dir: Path, timeout: float = 30.0) -> Path | None:
    """Download an image from a URL, caching it locally.

    Args:
        url: The image URL to download.
        cache_dir: Directory to cache downloaded images.
        timeout: HTTP request timeout in seconds.

    Returns:
        Path to the cached image file, or None if download failed.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    filename = _url_to_cache_filename(url)
    cached_path = cache_dir / filename

    # Return cached file if it exists
    if cached_path.exists() and cached_path.stat().st_size > 0:
        logger.debug(f"Cache hit: {url} -> {cached_path.name}")
        return cached_path

    # Download the image
    try:
        logger.debug(f"Downloading: {url}")
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        cached_path.write_bytes(response.content)
        logger.debug(f"Downloaded: {url} -> {cached_path.name} ({len(response.content):,} bytes)")
        return cached_path

    except httpx.HTTPError as e:
        logger.warning(f"Failed to download image: {url} — {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error downloading image: {url} — {e}")
        return None


def download_all_images(
    urls: list[str],
    cache_dir: Path,
    timeout: float = 30.0,
) -> dict[str, Path | None]:
    """Download multiple images, returning a mapping of URL -> local path.

    Args:
        urls: List of image URLs to download.
        cache_dir: Directory to cache downloaded images.
        timeout: HTTP request timeout in seconds.

    Returns:
        Dict mapping each URL to its local cached path (or None if failed).
    """
    results: dict[str, Path | None] = {}
    total = len(urls)

    for i, url in enumerate(urls, 1):
        logger.info(f"   Downloading image {i}/{total}...")
        results[url] = download_image(url, cache_dir, timeout)

    succeeded = sum(1 for p in results.values() if p is not None)
    logger.info(f"   Downloaded {succeeded}/{total} images successfully")

    return results
