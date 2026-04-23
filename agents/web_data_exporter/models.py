"""Data models for the Web Data Exporter agent."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class DataLayout(str, Enum):
    """How the data is structured in the HTML."""

    TABLE = "table"
    SECTIONS = "sections"
    LIST = "list"
    MIXED = "mixed"


@dataclass(frozen=True)
class ExportConfig:
    """Configuration for a data export job."""

    url: str | None = None
    local_html_path: Path | str | None = None
    output_filename: str | None = None  # Auto-derived from URL or local path if None

    def __post_init__(self) -> None:
        url_set = self.url is not None and bool(self.url.strip())
        local_set = self.local_html_path is not None and bool(
            str(self.local_html_path).strip()
        )
        if url_set and local_set:
            raise ValueError("Provide only one of 'url' or 'local_html_path'.")
        if not url_set and not local_set:
            raise ValueError("Provide either 'url' or 'local_html_path'.")

    def source_descriptor(self) -> str:
        """URL or resolved filesystem path for logging and export metadata."""
        if self.url is not None and self.url.strip():
            return self.url.strip()
        p = Path(self.local_html_path)  # type: ignore[arg-type]
        return str(p.resolve())

    def derive_output_filename(self) -> str:
        """Generate an output filename from the URL if not explicitly set."""
        if self.output_filename:
            return self.output_filename

        if self.local_html_path is not None:
            name = Path(self.local_html_path).stem
            name = name.replace("-", "_").replace("%20", "_")
            if not name.endswith(".json"):
                name += ".json"
            return name

        from urllib.parse import urlparse

        assert self.url is not None
        parsed = urlparse(self.url)
        # Use the path segments to create a meaningful name
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if path_parts:
            name = "_".join(path_parts[-2:]) if len(path_parts) > 1 else path_parts[-1]
        else:
            name = parsed.netloc.replace(".", "_")

        # Clean up the name
        name = name.replace("-", "_").replace("%20", "_")
        if not name.endswith(".json"):
            name += ".json"
        return name


@dataclass(frozen=True)
class AnalysisResult:
    """Result of the HTML structure analysis step."""

    data_layout: DataLayout
    subject: str  # What the data is about (e.g., "capital cities by elevation")
    columns: list[str]  # Identified data columns/fields
    strategy: str  # Description of the extraction strategy
    notes: str = ""  # Any additional notes for the script generator


@dataclass(frozen=True)
class ExportResult:
    """Result of a completed data export."""

    json_path: Path
    record_count: int
    columns: list[str]
    source_url: str
    errors: list[str] = field(default_factory=list)
