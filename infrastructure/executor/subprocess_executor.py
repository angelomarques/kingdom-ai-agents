"""Subprocess-based script executor implementation."""

import logging
import subprocess
import sys
from pathlib import Path

from core.executor.base import ExecutionResult, ScriptExecutor, ScriptExecutionError

logger = logging.getLogger(__name__)


class SubprocessExecutor(ScriptExecutor):
    """Execute Python scripts via subprocess.

    Runs generated scripts in a child process with timeout protection.
    The script runs with the same Python interpreter as the parent process.
    """

    def __init__(self, working_dir: Path | None = None):
        """Initialize the executor.

        Args:
            working_dir: Working directory for script execution.
                         Defaults to the script's parent directory.
        """
        self._working_dir = working_dir

    def execute(
        self,
        script_path: Path,
        args: list[str] | None = None,
        timeout_seconds: int = 60,
    ) -> ExecutionResult:
        """Execute a Python script via subprocess."""
        if not script_path.exists():
            raise ScriptExecutionError(f"Script not found: {script_path}")

        if not script_path.suffix == ".py":
            raise ScriptExecutionError(f"Expected a .py file, got: {script_path}")

        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)

        cwd = self._working_dir or script_path.parent

        logger.info(f"Executing script: {script_path.name}")
        logger.debug(f"Command: {' '.join(cmd)}")
        logger.debug(f"Working directory: {cwd}")
        logger.debug(f"Timeout: {timeout_seconds}s")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=str(cwd),
            )
        except subprocess.TimeoutExpired as e:
            raise ScriptExecutionError(
                f"Script timed out after {timeout_seconds} seconds: {script_path.name}"
            ) from e
        except OSError as e:
            raise ScriptExecutionError(
                f"Failed to execute script {script_path.name}: {e}"
            ) from e

        execution_result = ExecutionResult(
            stdout=result.stdout,
            stderr=result.stderr,
            return_code=result.returncode,
        )

        if execution_result.success:
            logger.info(f"Script executed successfully: {script_path.name}")
        else:
            logger.warning(
                f"Script failed with return code {result.returncode}: "
                f"{script_path.name}\nstderr: {result.stderr[:500]}"
            )

        return execution_result
