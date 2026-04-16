"""Data models for the JSON Schema Transformer agent."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TransformConfig:
    """Configuration for a JSON transformation job.

    The input directory must contain:
        - raw-data.json: The source data to transform.
        - schema.json: The target schema describing the desired output format.

    The output file (output.json) is written to the same directory.
    """

    input_dir: Path

    @property
    def raw_data_path(self) -> Path:
        return self.input_dir / "raw-data.json"

    @property
    def schema_path(self) -> Path:
        return self.input_dir / "schema.json"

    @property
    def output_path(self) -> Path:
        return self.input_dir / "output.json"

    def validate(self) -> None:
        """Validate that the required input files exist.

        Raises:
            FileNotFoundError: If raw-data.json or schema.json is missing.
        """
        if not self.input_dir.is_dir():
            raise FileNotFoundError(
                f"Input directory does not exist: {self.input_dir}"
            )
        if not self.raw_data_path.exists():
            raise FileNotFoundError(
                f"raw-data.json not found in: {self.input_dir}"
            )
        if not self.schema_path.exists():
            raise FileNotFoundError(
                f"schema.json not found in: {self.input_dir}"
            )


@dataclass(frozen=True)
class FieldMapping:
    """Describes how a single output field is derived from the raw data."""

    target_field: str
    source_fields: list[str]
    transformation: str  # e.g., "concatenate", "rename", "format", "compute"
    description: str


@dataclass(frozen=True)
class TransformAnalysis:
    """Result of the LLM's analysis of the transformation requirements."""

    field_mappings: list[FieldMapping]
    sorting: str  # Sorting instructions (empty string if none)
    notes: str  # Additional observations or edge cases


@dataclass(frozen=True)
class TransformResult:
    """Result of a completed JSON transformation."""

    json_path: Path
    record_count: int
    columns: list[str]
    errors: list[str] = field(default_factory=list)
