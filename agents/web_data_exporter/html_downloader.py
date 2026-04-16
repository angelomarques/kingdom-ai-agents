"""HTML downloader for the Web Data Exporter agent."""

import logging
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Default headers to mimic a regular browser request
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class HTMLDownloadError(Exception):
    """Raised when HTML download fails."""

    pass


def download_html(url: str, output_dir: Path, timeout: int = 30) -> Path:
    """Download an HTML page and save it to the output directory.

    Args:
        url: The URL to download.
        output_dir: Directory to save the HTML file.
        timeout: HTTP request timeout in seconds.

    Returns:
        Path to the saved HTML file.

    Raises:
        HTMLDownloadError: If the download fails.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate a filename from the URL
    filename = _url_to_filename(url)
    output_path = output_dir / filename

    logger.info(f"Downloading HTML from: {url}")

    try:
        with httpx.Client(
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTMLDownloadError(
            f"HTTP {e.response.status_code} error downloading {url}"
        ) from e
    except httpx.RequestError as e:
        raise HTMLDownloadError(f"Failed to download {url}: {e}") from e

    # Detect encoding
    encoding = response.encoding or "utf-8"
    html_content = response.content.decode(encoding, errors="replace")

    output_path.write_text(html_content, encoding="utf-8")

    logger.info(
        f"Saved HTML ({len(html_content):,} chars) to: {output_path.name}"
    )

    return output_path


def _url_to_filename(url: str) -> str:
    """Convert a URL to a safe filename."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]

    if path_parts:
        name = "_".join(path_parts[-2:]) if len(path_parts) > 1 else path_parts[-1]
    else:
        name = parsed.netloc.replace(".", "_")

    # Keep only safe characters
    name = re.sub(r"[^\w\-]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")

    if not name:
        name = "page"

    return f"{name}.html"
