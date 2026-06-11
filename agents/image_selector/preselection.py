"""Tag-to-title matching for image pre-selection."""

from __future__ import annotations

import re
import unicodedata

from agents.image_selector.models import ImageItem, Slide

RANK_PREFIX = re.compile(r"^#\d+:\s*")
# Strip trailing flag emojis and other symbols (keep letters, numbers, spaces, hyphens).
_TRAILING_SYMBOLS = re.compile(r"[\s\U0001F1E0-\U0001F1FF\U0001F300-\U0001FAFF]+$")

_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "city",
        "town",
        "urban",
        "world",
        "most",
        "best",
        "top",
    }
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _normalize_text(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    folded = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return " ".join(ascii_text.lower().split())


def _extract_subject(title: str) -> tuple[str, list[str]]:
    """Return normalized subject phrase and significant tokens from a slide title."""
    subject = RANK_PREFIX.sub("", title).strip()
    subject = _TRAILING_SYMBOLS.sub("", subject).strip()
    subject_phrase = _normalize_text(subject)

    tokens = [
        token
        for token in _WORD_RE.findall(subject_phrase)
        if len(token) >= 3 and token not in _STOPWORDS
    ]
    return subject_phrase, tokens


def _normalize_tags(tags: list[str]) -> tuple[set[str], str]:
    """Return individual normalized tags and combined tag text for substring checks."""
    normalized_tags: set[str] = set()
    combined_parts: list[str] = []

    for raw_tag in tags:
        normalized = _normalize_text(raw_tag)
        if not normalized:
            continue

        combined_parts.append(normalized)
        normalized_tags.add(normalized)

        for token in _WORD_RE.findall(normalized):
            if len(token) >= 3:
                normalized_tags.add(token)

    return normalized_tags, " ".join(combined_parts)


def score_image(slide: Slide, image_item: ImageItem) -> float:
    """Score how well an image's tags match the slide title (0.0–1.0)."""
    subject_phrase, subject_tokens = _extract_subject(slide.title)
    if not subject_phrase:
        return 0.0

    normalized_tags, combined_tags = _normalize_tags(image_item.tags)
    if not normalized_tags and not combined_tags:
        return 0.0

    # Exact tag equals subject phrase, or multi-word phrase appears as a tag.
    if subject_phrase in normalized_tags:
        return 1.0

    # Subject phrase substring in any tag (common for Pexels alt text).
    if subject_phrase and combined_tags and subject_phrase in combined_tags:
        return 0.85

    if not subject_tokens:
        return 0.0

    matched_tokens = sum(1 for token in subject_tokens if token in normalized_tags)
    if matched_tokens == len(subject_tokens):
        return 0.75

    ratio = matched_tokens / len(subject_tokens)
    if ratio >= 0.70:
        return ratio

    return 0.0


def suggest_image_index(slide: Slide, *, threshold: float = 0.70) -> int | None:
    """Return index of best-matching image, or None if below threshold / ambiguous."""
    if not slide.images:
        return None

    scored: list[tuple[int, float]] = [
        (idx, score_image(slide, image)) for idx, image in enumerate(slide.images)
    ]
    scored.sort(key=lambda item: item[1], reverse=True)

    best_idx, best_score = scored[0]
    if best_score < threshold:
        return None

    if len(scored) > 1:
        second_score = scored[1][1]
        if second_score >= threshold and (best_score - second_score) <= 0.05:
            return None

    return best_idx


def tag_matches_slide_title(title: str, raw_tag: str) -> bool:
    """Return True if a displayed tag matches the slide subject."""
    subject_phrase, subject_tokens = _extract_subject(title)
    normalized_tag = _normalize_text(raw_tag)
    if not normalized_tag or not subject_phrase:
        return False

    if normalized_tag == subject_phrase:
        return True

    if subject_phrase in normalized_tag:
        return True

    if subject_tokens and normalized_tag in subject_tokens:
        return True

    return False
