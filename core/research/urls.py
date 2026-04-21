"""URL helpers for research validation."""

from urllib.parse import urlparse, urlunparse


def normalize_http_url(url: str) -> str:
    """Normalize a http(s) URL for comparisons (scheme/host casing, trailing slash on path)."""
    raw = url.strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))
