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

    url: str
    output_filename: str | None = None  # Auto-derived from URL if None

    def derive_output_filename(self) -> str:
        """Generate an output filename from the URL if not explicitly set."""
        if self.output_filename:
            return self.output_filename

        from urllib.parse import urlparse

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
