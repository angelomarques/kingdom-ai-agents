"""Abstract base class for script executors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExecutionResult:
    """Result of executing a script."""

    stdout: str
    stderr: str
    return_code: int

    @property
    def success(self) -> bool:
        return self.return_code == 0


class ScriptExecutor(ABC):
    """Abstract interface for executing generated scripts.

    Implement this to add support for different execution strategies
    (e.g., subprocess, MCP server, Docker container).
    """

    @abstractmethod
    def execute(
        self,
        script_path: Path,
        args: list[str] | None = None,
        timeout_seconds: int = 60,
    ) -> ExecutionResult:
        """Execute a Python script and return the result.

        Args:
            script_path: Path to the Python script to execute.
            args: Optional command-line arguments for the script.
            timeout_seconds: Maximum execution time in seconds.

        Returns:
            ExecutionResult with stdout, stderr, and return code.

        Raises:
            ScriptExecutionError: If execution fails (timeout, missing file, etc.).
        """
        ...


class ScriptExecutionError(Exception):
    """Raised when script execution fails."""

    pass
