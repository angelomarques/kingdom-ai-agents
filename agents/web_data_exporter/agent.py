"""Web Data Exporter Agent — Main pipeline orchestrator."""

import json
import logging
from pathlib import Path

from core.executor.base import ScriptExecutor, ScriptExecutionError
from core.llm.base import LLMProvider, LLMProviderError
from core.llm.models import LLMRequest

from agents.web_data_exporter.html_downloader import download_html, HTMLDownloadError
from agents.web_data_exporter.models import (
    AnalysisResult,
    DataLayout,
    ExportConfig,
    ExportResult,
)
from agents.web_data_exporter.prompts import (
    ANALYSIS_SYSTEM_INSTRUCTION,
    SCRIPT_GENERATION_SYSTEM_INSTRUCTION,
    build_analysis_prompt,
    build_script_generation_prompt,
)

logger = logging.getLogger(__name__)


class WebDataExporterAgent:
    """Agent that exports structured data from web pages to JSON files.

    Pipeline:
        1. Download the HTML page
        2. Analyze HTML structure with LLM (identify data layout, columns)
        3. Generate a Python extraction script with LLM
        4. Execute the generated script
        5. Save the resulting JSON to the output directory
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        script_executor: ScriptExecutor,
        workspace_dir: Path,
        output_dir: Path,
    ):
        """Initialize the agent.

        Args:
            llm_provider: LLM provider for analysis and code generation.
            script_executor: Executor for running generated scripts.
            workspace_dir: Temporary workspace for HTML files and scripts.
            output_dir: Final output directory for JSON files.
        """
        self._llm = llm_provider
        self._executor = script_executor
        self._workspace_dir = workspace_dir
        self._output_dir = output_dir

        # Ensure directories exist
        self._workspace_dir.mkdir(parents=True, exist_ok=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, config: ExportConfig) -> ExportResult:
        """Run the full export pipeline.

        Args:
            config: Export configuration (URL, output filename).

        Returns:
            ExportResult with the path to the JSON file and metadata.

        Raises:
            Various exceptions if any step fails.
        """
        logger.info(f"{'=' * 60}")
        logger.info(f"Web Data Exporter Agent")
        logger.info(f"URL: {config.url}")
        logger.info(f"{'=' * 60}")

        # Step 1: Download HTML
        logger.info("\n📥 Step 1: Downloading HTML...")
        html_path = self._download_html(config.url)
        html_content = html_path.read_text(encoding="utf-8")
        logger.info(f"   Downloaded {len(html_content):,} characters")

        # Step 2: Analyze HTML structure
        logger.info("\n🔍 Step 2: Analyzing HTML structure...")
        analysis = self._analyze_html(html_content)
        logger.info(f"   Subject: {analysis.subject}")
        logger.info(f"   Layout: {analysis.data_layout.value}")
        logger.info(f"   Columns: {', '.join(analysis.columns)}")
        logger.info(f"   Strategy: {analysis.strategy}")

        # Step 3: Generate extraction script
        logger.info("\n🛠️  Step 3: Generating extraction script...")
        script_path = self._generate_script(html_content, analysis)
        logger.info(f"   Script saved to: {script_path.name}")

        # Step 4: Execute the script
        logger.info("\n⚡ Step 4: Executing extraction script...")
        output_filename = config.derive_output_filename()
        json_output_path = self._output_dir / output_filename
        result = self._execute_script(script_path, html_path, json_output_path)

        # Step 5: Validate and return result
        logger.info("\n✅ Step 5: Validating output...")
        export_result = self._validate_output(json_output_path, config.url, analysis)
        logger.info(f"   Records exported: {export_result.record_count}")
        logger.info(f"   Output file: {export_result.json_path}")
        logger.info(f"\n{'=' * 60}")
        logger.info("Export complete!")
        logger.info(f"{'=' * 60}")

        return export_result

    def _download_html(self, url: str) -> Path:
        """Step 1: Download the HTML page."""
        try:
            return download_html(url, self._workspace_dir)
        except HTMLDownloadError as e:
            logger.error(f"Failed to download HTML: {e}")
            raise

    def _analyze_html(self, html_content: str) -> AnalysisResult:
        """Step 2: Use LLM to analyze the HTML structure."""
        request = LLMRequest(
            prompt=build_analysis_prompt(html_content),
            system_instruction=ANALYSIS_SYSTEM_INSTRUCTION,
        )

        try:
            response = self._llm.generate(request)
        except LLMProviderError as e:
            logger.error(f"LLM analysis failed: {e}")
            raise

        # Parse the LLM's JSON response
        return self._parse_analysis_response(response.text)

    def _parse_analysis_response(self, response_text: str) -> AnalysisResult:
        """Parse the LLM's JSON response into an AnalysisResult."""
        # Strip any markdown code fences the LLM might add despite instructions
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (code fences)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM analysis response as JSON: {e}")
            logger.debug(f"Raw response:\n{response_text[:1000]}")
            raise ValueError(
                f"LLM returned invalid JSON for analysis. Response: {response_text[:200]}..."
            ) from e

        # Map data_layout string to enum
        layout_str = data.get("data_layout", "mixed").lower()
        try:
            data_layout = DataLayout(layout_str)
        except ValueError:
            logger.warning(f"Unknown data layout '{layout_str}', defaulting to MIXED")
            data_layout = DataLayout.MIXED

        return AnalysisResult(
            data_layout=data_layout,
            subject=data.get("subject", "Unknown"),
            columns=data.get("columns", []),
            strategy=data.get("strategy", ""),
            notes=data.get("notes", ""),
        )

    def _generate_script(
        self, html_content: str, analysis: AnalysisResult
    ) -> Path:
        """Step 3: Use LLM to generate a Python extraction script."""
        request = LLMRequest(
            prompt=build_script_generation_prompt(
                html_content=html_content,
                analysis_subject=analysis.subject,
                analysis_data_layout=analysis.data_layout.value,
                analysis_columns=analysis.columns,
                analysis_strategy=analysis.strategy,
                analysis_notes=analysis.notes,
            ),
            system_instruction=SCRIPT_GENERATION_SYSTEM_INSTRUCTION,
            model="gemini-3-flash-preview",
        )

        try:
            response = self._llm.generate(request)
        except LLMProviderError as e:
            logger.error(f"LLM script generation failed: {e}")
            raise

        # Clean up the response — remove code fences if present
        script_code = response.text.strip()
        if script_code.startswith("```"):
            lines = script_code.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            script_code = "\n".join(lines)

        # Save the script to workspace
        script_path = self._workspace_dir / "extract_data.py"
        script_path.write_text(script_code, encoding="utf-8")

        logger.debug(f"Generated script ({len(script_code)} chars):\n{script_code[:500]}...")

        return script_path

    def _execute_script(
        self, script_path: Path, html_path: Path, json_output_path: Path
    ) -> str:
        """Step 4: Execute the generated extraction script."""
        try:
            result = self._executor.execute(
                script_path=script_path,
                args=[str(html_path), str(json_output_path)],
                timeout_seconds=60,
            )
        except ScriptExecutionError as e:
            logger.error(f"Script execution failed: {e}")
            raise

        if result.stdout:
            logger.info(f"   Script output: {result.stdout.strip()}")

        if not result.success:
            error_msg = (
                f"Extraction script failed with return code {result.return_code}.\n"
                f"stderr: {result.stderr[:1000]}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        return result.stdout

    def _validate_output(
        self, json_path: Path, source_url: str, analysis: AnalysisResult
    ) -> ExportResult:
        """Step 5: Validate the output JSON and return the result."""
        if not json_path.exists():
            raise FileNotFoundError(
                f"Expected output JSON not found at: {json_path}"
            )

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Output JSON is invalid: {e}") from e

        # Determine record count and columns
        if isinstance(data, list):
            record_count = len(data)
            columns = list(data[0].keys()) if data else []
        elif isinstance(data, dict):
            # Maybe the data is nested under a key
            # Try to find the main data array
            for key, value in data.items():
                if isinstance(value, list) and value:
                    record_count = len(value)
                    columns = list(value[0].keys()) if value else []
                    break
            else:
                record_count = 1
                columns = list(data.keys())
        else:
            record_count = 0
            columns = []

        errors = []
        if record_count == 0:
            errors.append("No records found in output JSON")

        return ExportResult(
            json_path=json_path,
            record_count=record_count,
            columns=columns,
            source_url=source_url,
            errors=errors,
        )
