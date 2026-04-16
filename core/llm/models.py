"""Data models for LLM requests and responses."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMRequest:
    """Represents a request to an LLM provider."""

    prompt: str
    system_instruction: str | None = None
    model: str | None = None  # None = use provider default
    temperature: float | None = None


@dataclass(frozen=True)
class LLMResponse:
    """Represents a response from an LLM provider."""

    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    metadata: dict = field(default_factory=dict)
